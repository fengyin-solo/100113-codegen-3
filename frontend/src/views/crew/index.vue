<template>
  <section class="page" data-module="crew">
    <header class="page-head">
      <div>
        <h2>船员换班管理</h2>
        <p class="page-desc">按随船人员登记换班计划与登离船时间，按所属船舶划分归属；只有本船值班人员和船员管理员能提交，其他账号仅可查看。</p>
      </div>
    </header>

    <!-- 身份切换：演示按所属船舶的归属权限 -->
    <div class="identity-bar">
      <label class="identity-select">
        <span>当前账号</span>
        <select v-model.number="accountId" @change="onAccountChange">
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.姓名 }}（{{ acc.角色 }}{{ acc.所属船舶 ? ' · ' + acc.所属船舶 : ' · 全船舶' }}）
          </option>
        </select>
      </label>
      <span v-if="currentAccount" class="identity-role" :class="{ readonly: !canSubmitAny }">
        {{ currentAccount.姓名 }} · {{ currentAccount.角色
        }}<template v-if="currentAccount.所属船舶"> · 归属{{ currentAccount.所属船舶 }}</template>
      </span>
      <span v-if="!canSubmitAny" class="identity-tip">该账号为只读账号，只能查看换班记录，不能登记或确认</span>
      <span v-else-if="currentAccount?.角色 === '值班人员'" class="identity-tip">只能提交本船（{{ currentAccount?.所属船舶 }}）的换班计划</span>
      <span v-else class="identity-tip">船员管理员可代办所有船舶的换班计划</span>
    </div>

    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 换班计划 -->
    <div v-if="activeTab === 'plans'">
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">待确认计划</span>
          <strong class="stat-value">{{ pendingCount }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">已确认计划</span>
          <strong class="stat-value">{{ confirmedCount }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">证件过期随船人员</span>
          <strong class="stat-value warn">{{ expiredList.length }}</strong>
        </article>
      </div>

      <form class="filter-bar" @submit.prevent="loadPlans">
        <label class="filter-item">
          <span>所属船舶</span>
          <select v-model="planFilter.vessel">
            <option value="">全部船舶</option>
            <option v-for="v in vessels" :key="v" :value="v">{{ v }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>状态</span>
          <select v-model="planFilter.status">
            <option value="">全部状态</option>
            <option value="待确认">待确认</option>
            <option value="已确认">已确认</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetPlanFilter">重置条件</button>
        <button v-if="canSubmitAny" class="btn primary" type="button" @click="openCreate">登记换班计划</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th>换班编号</th>
            <th>所属船舶</th>
            <th>计划登船时间</th>
            <th>计划离船时间</th>
            <th>登船人员</th>
            <th>离船人员</th>
            <th>人数（登/离）</th>
            <th>状态</th>
            <th>提交/确认</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in plans" :key="String(row.id)">
            <td>{{ row.换班编号 }}</td>
            <td>{{ row.所属船舶 }}</td>
            <td>{{ row.计划登船时间 }}</td>
            <td>{{ row.计划离船时间 }}</td>
            <td>{{ (row.登船人员 ?? []).join('、') }}</td>
            <td>{{ (row.离船人员 ?? []).join('、') }}</td>
            <td>{{ row.登船人数 }} / {{ row.离船人数 }}</td>
            <td>
              <span class="status-tag" :class="row.状态 === '已确认' ? 'ok' : 'pending'">{{ row.状态 }}</span>
            </td>
            <td>
              <span v-if="row.状态 === '已确认'">{{ row.确认人 }} 于 {{ row.确认时间 }}</span>
              <span v-else>{{ row.提交人 }}（{{ row.提交人角色 }}）提交</span>
            </td>
            <td class="row-actions">
              <button
                v-if="canSubmitVessel(row.所属船舶) && row.状态 === '待确认'"
                class="link"
                type="button"
                @click="confirmPlan(row)"
              >
                确认换班
              </button>
              <span v-else-if="row.状态 === '已确认'" class="muted-text">已生效</span>
              <span v-else class="muted-text">无权限</span>
            </td>
          </tr>
          <tr v-if="!plans.length">
            <td colspan="10" class="empty-state">暂无换班计划，可由本船值班人员或船员管理员登记</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot">
        <span>共 {{ planTotal }} 条换班计划</span>
        <span v-if="message" :class="messageOk ? 'ok-text' : 'error-text'">{{ message }}</span>
      </footer>
    </div>

    <!-- 登离船台账 -->
    <div v-if="activeTab === 'records'">
      <div class="notice" :class="consistencyOk ? 'notice-ok' : 'notice-warn'">
        <strong>列表与登离船记录核对：</strong>
        {{ consistencyOk ? '已确认换班计划与登离船记录完全一致' : '存在计划与台账对不上的记录，请见下表' }}
      </div>
      <table class="data-table" style="margin-bottom:12px">
        <thead>
          <tr><th>换班编号</th><th>所属船舶</th><th>状态</th><th>计划登/离</th><th>台账登/离</th><th>核对</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in consistencyChecks" :key="c.换班编号">
            <td>{{ c.换班编号 }}</td>
            <td>{{ c.所属船舶 }}</td>
            <td>{{ c.状态 }}</td>
            <td>{{ c.计划登船人数 }} / {{ c.计划离船人数 }}</td>
            <td>{{ c.台账登船记录 }} / {{ c.台账离船记录 }}</td>
            <td>
              <span class="status-tag" :class="c.一致 ? 'ok' : 'pending'">{{ c.一致 ? '一致' : '不一致' }}</span>
            </td>
          </tr>
        </tbody>
      </table>

      <form class="filter-bar" @submit.prevent="loadRecords">
        <label class="filter-item">
          <span>所属船舶</span>
          <select v-model="recordFilter.vessel">
            <option value="">全部船舶</option>
            <option v-for="v in vessels" :key="v" :value="v">{{ v }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>方向</span>
          <select v-model="recordFilter.direction">
            <option value="">全部</option>
            <option value="登船">登船</option>
            <option value="离船">离船</option>
          </select>
        </label>
        <label class="filter-item">
          <span>姓名/编号</span>
          <input v-model="recordFilter.keyword" placeholder="按姓名或换班编号检索" />
        </label>
        <button class="btn" type="submit">查询</button>
      </form>
      <table class="data-table">
        <thead>
          <tr>
            <th>记录编号</th><th>换班编号</th><th>所属船舶</th><th>姓名</th><th>方向</th>
            <th>对接人员</th><th>登记时间</th><th>计划时间</th><th>经办人</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in records" :key="String(row.id)">
            <td>{{ row.记录编号 }}</td>
            <td>{{ row.换班编号 }}</td>
            <td>{{ row.所属船舶 }}</td>
            <td>{{ row.姓名 }}</td>
            <td>
              <span class="status-tag" :class="row.方向 === '登船' ? 'ok' : 'off'">{{ row.方向 }}</span>
            </td>
            <td>{{ row.对应离船人员 ?? row.对应登船人员 ?? '—' }}</td>
            <td>{{ row.登记时间 }}</td>
            <td>{{ row.计划时间 }}</td>
            <td>{{ row.经办人 }}</td>
          </tr>
          <tr v-if="!records.length">
            <td colspan="9" class="empty-state">暂无登离船记录</td>
          </tr>
        </tbody>
      </table>
      <footer class="page-foot"><span>共 {{ recordTotal }} 条登离船记录</span></footer>
    </div>

    <!-- 随船人员 -->
    <div v-if="activeTab === 'persons'">
      <div v-if="expiredList.length" class="expired-panel">
        <h3>证件过期随船人员（{{ expiredList.length }} 人，单独列出）</h3>
        <table class="data-table">
          <thead>
            <tr><th>工号</th><th>姓名</th><th>职务</th><th>所属船舶</th><th>证件类型</th><th>证件到期日</th><th>在船状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in expiredList" :key="String(p.id)">
              <td>{{ p.工号 }}</td><td>{{ p.姓名 }}</td><td>{{ p.职务 }}</td><td>{{ p.所属船舶 }}</td>
              <td>{{ p.证件类型 }}</td><td class="error-text">{{ p.证件到期日 }}</td><td>{{ p.在船状态 }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <form class="filter-bar" @submit.prevent="loadPersons">
        <label class="filter-item">
          <span>所属船舶</span>
          <select v-model="personFilter.vessel">
            <option value="">全部船舶</option>
            <option v-for="v in vessels" :key="v" :value="v">{{ v }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>姓名/工号</span>
          <input v-model="personFilter.keyword" placeholder="按姓名或工号检索" />
        </label>
        <button class="btn" type="submit">查询</button>
      </form>
      <table class="data-table">
        <thead>
          <tr><th>工号</th><th>姓名</th><th>职务</th><th>所属船舶</th><th>证件类型</th><th>证件到期日</th><th>证件状态</th><th>在船状态</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in persons" :key="String(p.id)">
            <td>{{ p.工号 }}</td>
            <td>{{ p.姓名 }}</td>
            <td>{{ p.职务 }}</td>
            <td>{{ p.所属船舶 }}</td>
            <td>{{ p.证件类型 }}</td>
            <td>{{ p.证件到期日 }}</td>
            <td>
              <span class="status-tag" :class="p.证件状态 === '已过期' ? 'pending' : 'ok'">{{ p.证件状态 }}</span>
            </td>
            <td>
              <span class="status-tag" :class="p.在船状态 === '在船' ? 'ok' : 'off'">{{ p.在船状态 }}</span>
            </td>
          </tr>
          <tr v-if="!persons.length">
            <td colspan="8" class="empty-state">暂无随船人员</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 值班本子（既有记录，只读） -->
    <div v-if="activeTab === 'duty'">
      <div class="notice notice-ok">既有值班记录照旧保留，此处仅可查看，不提供任何修改入口。</div>
      <table class="data-table">
        <thead>
          <tr><th>记录时间</th><th>所属船舶</th><th>值班人员</th><th>记录事项</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in dutyLogs" :key="String(row.id)">
            <td>{{ row.记录时间 }}</td><td>{{ row.所属船舶 }}</td><td>{{ row.值班人员 }}</td><td>{{ row.记录事项 }}</td>
          </tr>
          <tr v-if="!dutyLogs.length">
            <td colspan="4" class="empty-state">暂无值班记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 登记换班计划 -->
    <div v-if="showCreate" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <h3>登记换班计划</h3>
        <div class="form-row">
          <label class="form-item">
            <span>所属船舶 *</span>
            <select v-model="form.vessel" @change="onFormVesselChange">
              <option value="" disabled>请选择船舶</option>
              <option v-for="v in vessels" :key="v" :value="v">{{ v }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>计划登船时间 *</span>
            <input v-model="form.plannedOn" type="datetime-local" />
          </label>
          <label class="form-item">
            <span>计划离船时间 *</span>
            <input v-model="form.plannedOff" type="datetime-local" />
          </label>
        </div>

        <div v-if="form.vessel" class="pick-grid">
          <div class="pick-col">
            <h4>登船人员（当前休班离船，{{ form.onNames.length }} 人）</h4>
            <label v-for="p in offBoardCandidates" :key="String(p.id)" class="pick-line">
              <input type="checkbox" :value="p.姓名" v-model="form.onNames" />
              <span>{{ p.姓名 }} · {{ p.职务 }}</span>
              <em v-if="p.证件状态 === '已过期'" class="warn">证件过期</em>
            </label>
            <p v-if="!offBoardCandidates.length" class="muted-text">没有可登船的休班人员</p>
          </div>
          <div class="pick-col">
            <h4>离船人员（当前在船，{{ form.offNames.length }} 人）</h4>
            <label v-for="p in onBoardCandidates" :key="String(p.id)" class="pick-line">
              <input type="checkbox" :value="p.姓名" v-model="form.offNames" />
              <span>{{ p.姓名 }} · {{ p.职务 }}</span>
              <em v-if="p.证件状态 === '已过期'" class="warn">证件过期</em>
            </label>
            <p v-if="!onBoardCandidates.length" class="muted-text">没有可离船的在船人员</p>
          </div>
        </div>

        <div class="count-bar" :class="countMismatch ? 'count-bad' : 'count-ok'">
          登船 <strong>{{ form.onNames.length }}</strong> 人 · 离船
          <strong>{{ form.offNames.length }}</strong> 人
          <span v-if="countMismatch">—— 人数对不上，提交将被拦下</span>
          <span v-else-if="form.onNames.length">—— 人数已对齐，可以提交</span>
        </div>

        <footer class="modal-foot">
          <span v-if="formError" class="error-text">{{ formError }}</span>
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="button" :disabled="countMismatch" @click="submitPlan">提交计划</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

const ENDPOINT = '/api/crew'
const ACCOUNT_STORAGE_KEY = 'crew.accountId'

type Account = { id: number; 账号: string; 姓名: string; 角色: string; 所属船舶: string | null }
type Plan = Record<string, any>
type PersonRow = {
  id: number
  工号: string
  姓名: string
  职务: string
  所属船舶: string
  证件类型: string
  证件到期日: string
  证件状态: string
  在船状态: string
}
type LedgerRow = Record<string, any>
type DutyRow = Record<string, any>
type ConsistencyCheck = {
  换班编号: string
  所属船舶: string
  状态: string
  计划登船人数: number
  计划离船人数: number
  台账登船记录: number
  台账离船记录: number
  一致: boolean
}

const tabs = [
  { key: 'plans', label: '换班计划' },
  { key: 'records', label: '登离船台账' },
  { key: 'persons', label: '随船人员' },
  { key: 'duty', label: '值班本子（只读）' },
] as const
type TabKey = (typeof tabs)[number]['key']

const activeTab = ref<TabKey>('plans')
const accounts = ref<Account[]>([])
const accountId = ref<number>(1)
const vessels = ['远洋之星', '远东荣耀']

const plans = ref<Plan[]>([])
const planTotal = ref(0)
const records = ref<LedgerRow[]>([])
const recordTotal = ref(0)
const persons = ref<PersonRow[]>([])
const expiredList = ref<PersonRow[]>([])
const dutyLogs = ref<DutyRow[]>([])
const consistencyChecks = ref<ConsistencyCheck[]>([])
const consistencyOk = ref(true)

const planFilter = ref({ vessel: '', status: '' })
const recordFilter = ref({ vessel: '', direction: '', keyword: '' })
const personFilter = ref({ vessel: '', keyword: '' })

const message = ref('')
const messageOk = ref(false)

const showCreate = ref(false)
const formError = ref('')
const form = ref({
  vessel: '',
  plannedOn: '',
  plannedOff: '',
  onNames: [] as string[],
  offNames: [] as string[],
})
const vesselPersons = ref<PersonRow[]>([])

const currentAccount = computed<Account | undefined>(() =>
  accounts.value.find((item) => item.id === accountId.value),
)
const canSubmitAny = computed(() => {
  const acc = currentAccount.value
  return !!acc && (acc.角色 === '船员管理员' || acc.角色 === '值班人员')
})

function canSubmitVessel(vessel: string): boolean {
  const acc = currentAccount.value
  if (!acc) return false
  if (acc.角色 === '船员管理员') return true
  return acc.角色 === '值班人员' && acc.所属船舶 === vessel
}

const pendingCount = computed(() => plans.value.filter((row) => row.状态 === '待确认').length)
const confirmedCount = computed(() => plans.value.filter((row) => row.状态 === '已确认').length)

const onBoardCandidates = computed(() =>
  vesselPersons.value
    .filter((p) => p.所属船舶 === form.value.vessel && p.在船状态 === '在船')
    .sort((a, b) => a.工号.localeCompare(b.工号)),
)
const offBoardCandidates = computed(() =>
  vesselPersons.value
    .filter((p) => p.所属船舶 === form.value.vessel && p.在船状态 !== '在船')
    .sort((a, b) => a.工号.localeCompare(b.工号)),
)
const countMismatch = computed(() => form.value.onNames.length !== form.value.offNames.length)

function flash(text: string, ok = false) {
  message.value = text
  messageOk.value = ok
}

async function loadAccounts() {
  const response = await request(`${ENDPOINT}/accounts`)
  if (response.ok) {
    const payload = await response.json()
    accounts.value = payload.items ?? []
    const saved = Number(window.localStorage.getItem(ACCOUNT_STORAGE_KEY))
    if (saved && accounts.value.some((acc) => acc.id === saved)) {
      accountId.value = saved
    }
  }
}

function onAccountChange() {
  window.localStorage.setItem(ACCOUNT_STORAGE_KEY, String(accountId.value))
  flash('')
}

function switchTab(key: TabKey) {
  activeTab.value = key
  flash('')
  if (key === 'records') void loadRecords()
  if (key === 'persons') void loadPersons()
  if (key === 'duty') void loadDutyLogs()
}

function resetPlanFilter() {
  planFilter.value = { vessel: '', status: '' }
  void loadPlans()
}

async function loadPlans() {
  const query = new URLSearchParams()
  if (planFilter.value.vessel) query.set('vessel', planFilter.value.vessel)
  if (planFilter.value.status) query.set('status', planFilter.value.status)
  const response = await request(`${ENDPOINT}/plans?${query.toString()}`)
  if (response.ok) {
    const payload = await response.json()
    plans.value = payload.items ?? []
    planTotal.value = payload.total ?? 0
  }
}

async function loadRecords() {
  const query = new URLSearchParams()
  if (recordFilter.value.vessel) query.set('vessel', recordFilter.value.vessel)
  if (recordFilter.value.direction) query.set('direction', recordFilter.value.direction)
  if (recordFilter.value.keyword) query.set('keyword', recordFilter.value.keyword)
  const [listResp, consResp] = await Promise.all([
    request(`${ENDPOINT}/records?${query.toString()}`),
    request(`${ENDPOINT}/records/consistency`),
  ])
  if (listResp.ok) {
    const payload = await listResp.json()
    records.value = payload.items ?? []
    recordTotal.value = payload.total ?? 0
  }
  if (consResp.ok) {
    const payload = await consResp.json()
    consistencyChecks.value = payload.checks ?? []
    consistencyOk.value = !!payload.ok
  }
}

async function loadPersons() {
  const query = new URLSearchParams()
  if (personFilter.value.vessel) query.set('vessel', personFilter.value.vessel)
  if (personFilter.value.keyword) query.set('keyword', personFilter.value.keyword)
  const [listResp, expiredResp] = await Promise.all([
    request(`${ENDPOINT}/persons?${query.toString()}`),
    request(`${ENDPOINT}/persons/expired`),
  ])
  if (listResp.ok) {
    persons.value = (await listResp.json()).items ?? []
  }
  if (expiredResp.ok) {
    expiredList.value = (await expiredResp.json()).items ?? []
  }
}

async function loadDutyLogs() {
  const response = await request(`${ENDPOINT}/duty-logs`)
  if (response.ok) {
    dutyLogs.value = (await response.json()).items ?? []
  }
}

async function loadVesselPersons(vessel: string) {
  const query = new URLSearchParams({ vessel })
  const response = await request(`${ENDPOINT}/persons?${query.toString()}`)
  if (response.ok) {
    vesselPersons.value = (await response.json()).items ?? []
  }
}

function openCreate() {
  const acc = currentAccount.value
  // 只读账号没有入口；值班人员默认锁定本船，管理员需要选船
  form.value = {
    vessel: acc?.角色 === '值班人员' && acc.所属船舶 ? acc.所属船舶 : '',
    plannedOn: '',
    plannedOff: '',
    onNames: [],
    offNames: [],
  }
  formError.value = ''
  showCreate.value = true
  if (form.value.vessel) void loadVesselPersons(form.value.vessel)
}

function closeCreate() {
  showCreate.value = false
  formError.value = ''
}

async function onFormVesselChange() {
  form.value.onNames = []
  form.value.offNames = []
  formError.value = ''
  if (form.value.vessel) await loadVesselPersons(form.value.vessel)
}

async function submitPlan() {
  formError.value = ''
  if (!form.value.vessel) {
    formError.value = '请选择所属船舶'
    return
  }
  if (!canSubmitVessel(form.value.vessel)) {
    formError.value = '当前账号无权提交该船的换班计划'
    return
  }
  if (!form.value.plannedOn || !form.value.plannedOff) {
    formError.value = '请填写计划登船时间与计划离船时间'
    return
  }
  if (countMismatch.value) {
    formError.value = `登船人数 ${form.value.onNames.length} 人与离船人数 ${form.value.offNames.length} 人对不上，不能提交`
    return
  }
  if (!form.value.onNames.length) {
    formError.value = '登船、离船名单都为空'
    return
  }
  const body = JSON.stringify({
    account_id: accountId.value,
    所属船舶: form.value.vessel,
    计划登船时间: form.value.plannedOn.replace('T', ' '),
    计划离船时间: form.value.plannedOff.replace('T', ' '),
    登船人员: form.value.onNames,
    离船人员: form.value.offNames,
  })
  const response = await request(`${ENDPOINT}/plans`, { method: 'POST', body })
  const payload = await response.json().catch(() => null)
  if (response.status === 403) {
    formError.value = payload?.detail ?? '越权提交已被拒绝'
    return
  }
  if (!response.ok || !payload?.ok) {
    formError.value = payload?.message ?? '换班计划未提交成功'
    return
  }
  showCreate.value = false
  flash(payload.message ?? '换班计划已登记', true)
  await Promise.all([loadPlans(), loadPersons()])
}

async function confirmPlan(row: Plan) {
  if (!canSubmitVessel(row.所属船舶)) {
    flash('当前账号无权确认该船的换班计划')
    return
  }
  const body = JSON.stringify({ account_id: accountId.value })
  const response = await request(`${ENDPOINT}/plans/${row.id}/confirm`, {
    method: 'POST',
    body,
  })
  const payload = await response.json().catch(() => null)
  if (response.status === 403) {
    flash(payload?.detail ?? '越权确认已被拒绝')
    return
  }
  if (!response.ok || !payload?.ok) {
    // 同一条计划重复确认只生效一次：服务端拒绝并说明，这里原样展示
    flash(payload?.message ?? '换班确认未生效')
    await loadPlans()
    return
  }
  flash(payload.message ?? '换班计划已确认', true)
  await Promise.all([loadPlans(), loadRecords(), loadPersons()])
}

onMounted(async () => {
  await loadAccounts()
  await Promise.all([loadPlans(), loadPersons(), loadDutyLogs()])
})
</script>

<style scoped>
.identity-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.identity-select span { display: block; font-size: 12px; color: var(--muted); }
.identity-select select { min-width: 280px; padding: 4px 6px; }
.identity-role { font-weight: 600; }
.identity-role.readonly { color: #b42318; }
.identity-tip { color: var(--muted); }
.tab-bar { display: flex; gap: 6px; margin-bottom: 12px; }
.tab-btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 6px 6px 0 0;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
}
.tab-btn.active { background: var(--brand); border-color: var(--brand); color: #fff; }
.status-tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.status-tag.ok { background: #e7f6ec; color: #1a7f37; }
.status-tag.pending { background: #fdecec; color: #b42318; }
.status-tag.off { background: #eef2f7; color: #475569; }
.muted-text { color: var(--muted); font-size: 12px; }
.warn { color: #b42318; font-style: normal; font-size: 12px; }
.ok-text { color: #1a7f37; }
.notice { border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 13px; }
.notice-ok { background: #e7f6ec; color: #1a7f37; border: 1px solid #b7e0c4; }
.notice-warn { background: #fdecec; color: #b42318; border: 1px solid #f3c2c2; }
.expired-panel {
  border: 1px solid #f3c2c2;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 14px;
  background: #fff7f7;
}
.expired-panel h3 { margin: 0 0 8px; font-size: 14px; color: #b42318; }
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  background: #fff;
  border-radius: 10px;
  width: 760px;
  max-width: 92vw;
  max-height: 88vh;
  overflow: auto;
  padding: 18px 20px;
}
.modal h3 { margin: 0 0 12px; }
.form-row { display: flex; gap: 12px; }
.form-item { flex: 1; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item select, .form-item input { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.pick-grid { display: flex; gap: 14px; margin-top: 14px; }
.pick-col { flex: 1; border: 1px solid var(--border); border-radius: 8px; padding: 10px; }
.pick-col h4 { margin: 0 0 8px; font-size: 13px; }
.pick-line { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
.pick-line input { margin: 0; }
.count-bar { margin-top: 12px; padding: 8px 12px; border-radius: 6px; font-size: 13px; }
.count-ok { background: #e7f6ec; color: #1a7f37; }
.count-bad { background: #fdecec; color: #b42318; }
.modal-foot { display: flex; justify-content: flex-end; gap: 10px; align-items: center; margin-top: 14px; }
.modal-foot .error-text { margin-right: auto; }
.btn:disabled { opacity: 0.55; cursor: not-allowed; }
</style>
