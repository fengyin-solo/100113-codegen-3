"""船员换班业务规则：归属权限、换人对数、幂等确认、证件过期与登离船台账都收在这里。

- 账号按所属船舶划分归属：只有本船值班人员或船员管理员能提交，其余账号只读。
- 一条换班计划重复确认只生效一次；登船人数与离船人数对不上直接拒绝并说明原因。
- 确认时同步生成登船/离船记录并回写随船人员在船状态，保证列表与台账一致。

既有值班记录（crew_duty_log）只供查看，不提供任何修改入口。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

# 随船人员、账号、换班计划、登离船记录、值班本子（只读）
PERSON_MODULE = "crew_person"
ACCOUNT_MODULE = "crew_account"
PLAN_MODULE = "crew_plan"
RECORD_MODULE = "crew_record"
DUTY_MODULE = "crew_duty_log"

SUBMIT_ROLES = {"值班人员", "船员管理员"}
PLAN_DRAFT = "待确认"
PLAN_CONFIRMED = "已确认"
ON_BOARD = "在船"
OFF_BOARD = "休班离船"
DIRECTION_ON = "登船"
DIRECTION_OFF = "离船"


class PermissionDenied(Exception):
    """越权提交：路由层据此返回 403，message 即展示给用户的拒绝原因。"""


def _today() -> date:
    return date.today()


def _parse_day(value: Any) -> date | None:
    # 登记时间统一是 "YYYY-MM-DD ..." 文本，取前 10 位按日期比较即可
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _is_expired(cert_expire: Any) -> bool:
    day = _parse_day(cert_expire)
    return day is not None and day < _today()


def _paginate(rows: list[dict[str, Any]], page: int, size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(rows)
    start = max(page - 1, 0) * size
    return rows[start:start + size], total


class CrewService:
    # ---------- 账号与权限 ----------
    def list_accounts(self) -> list[dict[str, Any]]:
        return store.rows(ACCOUNT_MODULE)

    def _account(self, account_id: Any) -> dict[str, Any] | None:
        try:
            target_id = int(account_id)
        except (TypeError, ValueError):
            return None
        return store.find(ACCOUNT_MODULE, target_id)

    def can_submit(self, account: dict[str, Any] | None, vessel: str) -> bool:
        """是否能提交该船的换班：船员管理员可管所有船，值班人员只能管本船。"""
        if not account or account.get("角色") not in SUBMIT_ROLES:
            return False
        if account.get("角色") == "船员管理员":
            return True
        return str(account.get("所属船舶") or "").strip() == str(vessel or "").strip()

    def _require_submit(self, account_id: Any, vessel: str) -> dict[str, Any]:
        """越权提交直接拒绝，并给出可读原因；路由层转成 403。"""
        account = self._account(account_id)
        if account is None:
            raise PermissionDenied(
                f"账号标识 {account_id} 无法识别，请先在右上角切换为已登记账号后再提交"
            )
        if account.get("角色") not in SUBMIT_ROLES:
            raise PermissionDenied(
                f"账号「{account.get('姓名')}」的角色是{account.get('角色')}，"
                "只能查看船员换班记录，不能提交或确认；"
                "如需办理，请联系本船值班人员或船员管理员"
            )
        if account.get("角色") == "值班人员" and str(account.get("所属船舶") or "").strip() != str(vessel or "").strip():
            raise PermissionDenied(
                f"账号「{account.get('姓名')}」归属「{account.get('所属船舶')}」，"
                f"不能代办「{vessel}」的换班：按所属船舶划分归属，只有本船值班人员和船员管理员能提交"
            )
        return account

    # ---------- 随船人员 ----------
    def list_persons(self, *, vessel: str | None = None, keyword: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows(PERSON_MODULE)
        if vessel:
            rows = [row for row in rows if row.get("所属船舶") == vessel]
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("姓名", "")) or keyword in str(row.get("工号", ""))
            ]
        return rows

    def expired_persons(self, *, vessel: str | None = None) -> list[dict[str, Any]]:
        """证件过期的随船人员单独列出，不阻塞换班，但要在提交前让经办人看见。"""
        return [
            dict(row, **{"证件状态": "已过期"})
            for row in self.list_persons(vessel=vessel)
            if _is_expired(row.get("证件到期日"))
        ]

    def on_board_persons(self, *, vessel: str | None = None) -> list[dict[str, Any]]:
        return [row for row in self.list_persons(vessel=vessel) if row.get("在船状态") == ON_BOARD]

    def _find_person(self, name: str, vessel: str) -> tuple[dict[str, Any] | None, str | None]:
        """按姓名在指定船舶的随船人员里找人，给出可读的不通过原因。"""
        name = str(name or "").strip()
        if not name:
            return None, "存在空姓名，请补齐登船/离船人员名单"
        matches = [row for row in self.list_persons(vessel=vessel) if str(row.get("姓名") or "").strip() == name]
        if not matches:
            return None, f"人员「{name}」不在「{vessel}」的随船人员登记里，不能纳入本船换班"
        return matches[0], None

    # ---------- 换班计划 ----------
    def list_plans(
        self,
        *,
        vessel: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(PLAN_MODULE)
        if vessel:
            rows = [row for row in rows if row.get("所属船舶") == vessel]
        if status:
            rows = [row for row in rows if row.get("状态") == status]
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)), reverse=True)
        return _paginate(rows, page, size)

    def get_plan(self, plan_id: int) -> dict[str, Any] | None:
        return store.find(PLAN_MODULE, plan_id)

    def create_plan(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        vessel = str(values.get("所属船舶") or "").strip()
        if not vessel:
            return None, "缺少必填字段：所属船舶"

        # 先做归属校验：越权提交要说明原因后拒绝
        account = self._require_submit(values.get("account_id"), vessel)

        planned_on = str(values.get("计划登船时间") or "").strip()
        planned_off = str(values.get("计划离船时间") or "").strip()
        if not planned_on or not planned_off:
            return None, "缺少必填字段：计划登船时间、计划离船时间"

        on_names = [str(n).strip() for n in (values.get("登船人员") or []) if str(n).strip()]
        off_names = [str(n).strip() for n in (values.get("离船人员") or []) if str(n).strip()]

        # 登船人数与离船人数对不上时挡住不让提交
        if len(on_names) != len(off_names):
            return None, (
                f"登船人数 {len(on_names)} 人与离船人数 {len(off_names)} 人对不上，"
                "换班必须一对一交接，人数不平不能提交，请调整名单后重试"
            )
        if not on_names:
            return None, "登船、离船名单都为空，没有可办理的换班人员"
        if len(set(on_names)) != len(on_names) or len(set(off_names)) != len(off_names):
            return None, "同一份名单里出现了重复人员，一名船员不能重复登船或离船"

        # 人员必须属于本船，且当前状态与动作匹配
        for name in on_names:
            person, reason = self._find_person(name, vessel)
            if reason:
                return None, reason
            if person and person.get("在船状态") == ON_BOARD:
                return None, f"登船人员「{name}」当前已在船上，不能重复登记登船"
        for name in off_names:
            person, reason = self._find_person(name, vessel)
            if reason:
                return None, reason
            if person and person.get("在船状态") != ON_BOARD:
                return None, f"离船人员「{name}」当前不在船上，无法办理离船"
        overlap = set(on_names) & set(off_names)
        if overlap:
            return None, f"人员「{'、'.join(sorted(overlap))}」同时出现在登船和离船名单里，请核对"

        rows = store.rows(PLAN_MODULE)
        next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        entry: dict[str, Any] = {
            "id": next_id,
            "换班编号": f"CRCH-{next_id:04d}",
            "所属船舶": vessel,
            "计划登船时间": planned_on,
            "计划离船时间": planned_off,
            "登船人员": on_names,
            "离船人员": off_names,
            "登船人数": len(on_names),
            "离船人数": len(off_names),
            "状态": PLAN_DRAFT,
            "提交人": account.get("姓名"),
            "提交人角色": account.get("角色"),
            "确认人": None,
            "确认时间": None,
            "实际登船时间": None,
            "实际离船时间": None,
        }
        rows.append(entry)
        return entry, f"换班计划 {entry['换班编号']} 已登记，等待本船值班人员或船员管理员确认"

    def confirm_plan(
        self,
        plan_id: int,
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(PLAN_MODULE, plan_id)
        if entry is None:
            return None, f"换班计划 {plan_id} 不存在或已归档"

        # 确认同样受归属限制
        account = self._require_submit(values.get("account_id"), entry["所属船舶"])

        # 同一条换班计划重复确认只生效一次
        if entry.get("状态") == PLAN_CONFIRMED:
            return None, (
                f"换班计划 {entry['换班编号']} 已在 {entry.get('确认时间')} 由"
                f"{entry.get('确认人')} 确认过，重复确认不再生效，登离船记录维持原记录"
            )

        on_names = list(entry.get("登船人员") or [])
        off_names = list(entry.get("离船人员") or [])
        if len(on_names) != len(off_names):
            # 正常创建入口挡不住这种情况，这里兜底，避免台账出现半条记录
            return None, (
                f"登船人数 {len(on_names)} 人与离船人数 {len(off_names)} 人对不上，"
                "不能确认，请先修正换班计划"
            )

        # 确认时再核一遍人员归属与在船状态，防止登记后人员状态变动
        for name in on_names:
            person, reason = self._find_person(name, entry["所属船舶"])
            if reason:
                return None, reason
            if person and person.get("在船状态") == ON_BOARD:
                return None, f"登船人员「{name}」已在船上，本次确认中止"
        for name in off_names:
            person, reason = self._find_person(name, entry["所属船舶"])
            if reason:
                return None, reason
            if person and person.get("在船状态") != ON_BOARD:
                return None, f"离船人员「{name}」当前不在船上，本次确认中止"

        actual_on = str(values.get("实际登船时间") or "").strip() or entry["计划登船时间"]
        actual_off = str(values.get("实际离船时间") or "").strip() or entry["计划离船时间"]
        confirmed_at = str(values.get("确认时间") or "").strip() or _today().isoformat()

        # 生成登离船记录并回写随船人员在船状态
        records = store.rows(RECORD_MODULE)
        next_record_id = max((int(row.get("id", 0)) for row in records), default=0) + 1
        for index, name in enumerate(on_names):
            records.append({
                "id": next_record_id,
                "记录编号": f"CRLG-{next_record_id:04d}",
                "换班编号": entry["换班编号"],
                "所属船舶": entry["所属船舶"],
                "姓名": name,
                "方向": DIRECTION_ON,
                "对应离船人员": off_names[index],
                "登记时间": actual_on,
                "计划时间": entry["计划登船时间"],
                "经办人": account.get("姓名"),
            })
            next_record_id += 1
        for index, name in enumerate(off_names):
            records.append({
                "id": next_record_id,
                "记录编号": f"CRLG-{next_record_id:04d}",
                "换班编号": entry["换班编号"],
                "所属船舶": entry["所属船舶"],
                "姓名": name,
                "方向": DIRECTION_OFF,
                "对应登船人员": on_names[index],
                "登记时间": actual_off,
                "计划时间": entry["计划离船时间"],
                "经办人": account.get("姓名"),
            })
            next_record_id += 1

        for name in on_names:
            person, _ = self._find_person(name, entry["所属船舶"])
            if person:
                person["在船状态"] = ON_BOARD
        for name in off_names:
            person, _ = self._find_person(name, entry["所属船舶"])
            if person:
                person["在船状态"] = OFF_BOARD

        entry["状态"] = PLAN_CONFIRMED
        entry["确认人"] = account.get("姓名")
        entry["确认时间"] = confirmed_at
        entry["实际登船时间"] = actual_on
        entry["实际离船时间"] = actual_off

        return entry, (
            f"换班计划 {entry['换班编号']} 已确认：登船 {len(on_names)} 人、离船 {len(off_names)} 人，"
            "登离船记录已同步生成"
        )

    # ---------- 登离船台账 ----------
    def list_records(
        self,
        *,
        vessel: str | None = None,
        direction: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(RECORD_MODULE)
        if vessel:
            rows = [row for row in rows if row.get("所属船舶") == vessel]
        if direction:
            rows = [row for row in rows if row.get("方向") == direction]
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("姓名", "")) or keyword in str(row.get("换班编号", ""))
            ]
        rows = sorted(rows, key=lambda row: int(row.get("id", 0)))
        return _paginate(rows, page, size)

    def consistency_report(self) -> dict[str, Any]:
        """核对换班计划列表与登离船记录是否一致：每条已确认计划必须有成对台账。"""
        checks: list[dict[str, Any]] = []
        ok = True
        for plan in store.rows(PLAN_MODULE):
            linked = [
                row for row in store.rows(RECORD_MODULE)
                if row.get("换班编号") == plan.get("换班编号")
            ]
            on_count = sum(1 for row in linked if row.get("方向") == DIRECTION_ON)
            off_count = sum(1 for row in linked if row.get("方向") == DIRECTION_OFF)
            expected_on = int(plan.get("登船人数") or 0) if plan.get("状态") == PLAN_CONFIRMED else 0
            expected_off = int(plan.get("离船人数") or 0) if plan.get("状态") == PLAN_CONFIRMED else 0
            plan_ok = on_count == expected_on and off_count == expected_off
            ok = ok and plan_ok
            checks.append({
                "换班编号": plan.get("换班编号"),
                "所属船舶": plan.get("所属船舶"),
                "状态": plan.get("状态"),
                "计划登船人数": int(plan.get("登船人数") or 0),
                "计划离船人数": int(plan.get("离船人数") or 0),
                "台账登船记录": on_count,
                "台账离船记录": off_count,
                "一致": plan_ok,
            })
        return {"ok": ok, "checks": checks}

    # ---------- 值班本子（既有记录，只读） ----------
    def list_duty_logs(self, *, vessel: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows(DUTY_MODULE)
        if vessel:
            rows = [row for row in rows if row.get("所属船舶") == vessel]
        return sorted(rows, key=lambda row: int(row.get("id", 0)))
