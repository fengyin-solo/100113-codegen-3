"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
船员换班相关的两个模块（crewchange、crewmember）额外落盘到本地 JSON，
刷新页面或重启服务后已确认的换班记录仍然保留，其余模块照旧只在内存里。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

# 需要落盘保留的模块：换班记录确认后不能因为刷新或重启丢失。
PERSIST_MODULES = {"crewchange", "crewmember"}

_env_data_dir = os.environ.get("APP_DATA_DIR", "").strip()
DATA_DIR = Path(_env_data_dir) if _env_data_dir else Path(__file__).resolve().parents[1] / "data"


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }
        for name in PERSIST_MODULES:
            saved = self._load_saved(name)
            if saved is not None:
                self._tables[name] = saved

    def _load_saved(self, module: str) -> list[dict[str, Any]] | None:
        """读取落盘数据；文件缺失或损坏时回退到示例数据，不影响启动。"""
        path = DATA_DIR / f"{module}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, list) else None

    def save(self, module: str) -> None:
        """把需要落盘的模块写进本地 JSON；不在落盘名单里的模块直接跳过。"""
        if module not in PERSIST_MODULES:
            return
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self.rows(module), ensure_ascii=False, indent=2)
            (DATA_DIR / f"{module}.json").write_text(payload, encoding="utf-8")
        except OSError:
            pass  # 落盘失败不拖垮本次请求，内存中的数据仍然有效

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
