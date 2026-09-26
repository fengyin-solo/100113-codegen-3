<template>
  <section class="page" data-module="crewchange">
    <header class="page-head">
      <div>
        <h2>船员换班管理</h2>
        <p class="page-desc">按随船人员登记换班计划与登离船时间，只有本船值班人员和船员管理员能提交，其他账号只能查看。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showForm = !showForm">登记换班计划</button>
        <button class="btn" type="button" @click="exportRows">导出换班记录</button>
      </div>
    </header>

    <div class="account-bar">
      <label class="filter-item">
        <span>当前账号</span>
        <select v-model="currentOperator">
          <option v-for="account in accounts" :key="account.姓名" :value="account.姓名">
            {{ account.姓名 }} · {{ account.角色 }}<template v-if="account.所属船舶"> · {{ account.所属船舶 }}</template>
          </option>
        </select>
      </label>
      <span class="account-hint">{{ accountHint }}</span>
    </div>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showForm" class="create-panel" @submit.prevent="submitCreate">
      <h3 class="panel-title">登记换班计划</h3>
      <div class="create-grid">
        <label class="filter-item">
          <span>所属船舶</span>
          <select v-model="form.vessel">
            <option v-for="vessel in vessels" :key="vessel" :value="vessel">{{ vessel }}</option>
          </select>
        </label>
        <label class="filter-item">
          <span>登船时间</span>
          <input v-model="form.boardTime" type="datetime-local" />
        </label>
        <label class="filter-item">
          <span>离船时间</span>
          <input v-model="form.leaveTime" type="datetime-local" />
        </label>
      </div>
      <div class="pick-grid">
        <div class="pick-box">
          <strong>登船人员（已选 {{ form.boarding.length }} 人）</strong>
          <label v-for="member in boardCandidates" :key="member.id" class="pick-item">
            <input v-model="form.boarding" type="checkbox" :value="member.姓名" />
            {{ member.姓名 }} · {{ member.职务 }}
          </label>
          <p v-if="!boardCandidates.length" class="empty-state">该船暂无待登船的随船人员</p>
        </div>
        <div class="pick-box">
          <strong>离船人员（已选 {{ form.leaving.length }} 人）</strong>
          <label v-for="member in leaveCandidates" :key="member.id" class="pick-item">
            <input v-model="form.leaving" type="checkbox" :value="member.姓名" />
            {{ member.姓名 }} · {{ member.职务 }}
          </label>
          <p v-if="!leaveCandidates.length" class="empty-state">该船暂无在船人员可离船</p>
        </div>
      </div>
      <p v-if="countMismatch" class="error-text">
        登船 {{ form.boarding.length }} 人、离船 {{ form.leaving.length }} 人，人数对不上将无法提交
      </p>
      <div class="page-actions">
        <button class="btn primary" type="submit">提交换班计划</button>
        <button class="btn ghost" type="button" @click="resetForm">清空重填</button>
      </div>
    </form>

    <section v-if="expiredCrew.length" class="expired-panel">
      <h3 class="panel-title">证件过期随船人员（{{ expiredCrew.length }} 人，需先安排换证）</h3>
      <table class="data-table">
        <thead>
          <tr><th>姓名</th><th>职务</th><th>所属船舶</th><th>证件类型</th><th>证件有效期</th><th>在船状态</th></tr>
        </thead>
        <tbody>
          <tr v-for="member in expiredCrew" :key="member.id">
            <td>{{ member.姓名 }}</td>
            <td>{{ member.职务 }}</td>
            <td>{{ member.所属船舶 }}</td>
            <td>{{ member.证件类型 }}</td>
            <td class="error-text">{{ member.证件有效期 }}</td>
            <td>{{ member.在船状态 }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>计划编号</span>
        <input v-model="filters.keyword" placeholder="按计划编号检索" />
      </label>
      <label class="filter-item">
        <span>所属船舶</span>
        <select v-model="filters.vessel">
          <option value="">全部船舶</option>
          <option v-for="vessel in vessels" :key="vessel" :value="vessel">{{ vessel }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>计划状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ displayCell(row, column) }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="runAction('确认换班', row)">确认换班</button>
            <button class="link" type="button" @click="runAction('取消换班', row)">取消换班</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无换班计划，可先登记换班计划</td>
        </tr>
      </tbody>
    </table>

    <h3 class="panel-title crew-title">随船人员名单（与已确认的登离船记录一致）</h3>
    <table class="data-table">
      <thead>
        <tr><th>姓名</th><th>职务</th><th>所属船舶</th><th>证件有效期</th><th>在船状态</th></tr>
      </thead>
      <tbody>
        <tr v-for="member in crew" :key="member.id">
          <td>{{ member.姓名 }}</td>
          <td>{{ member.职务 }}</td>
          <td>{{ member.所属船舶 }}</td>
          <td>{{ member.证件有效期 }}</td>
          <td>{{ member.在船状态 }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条换班计划</span>
      <span v-if="notice" class="ok-text">{{ notice }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, any>
type Account = { 姓名: string; 角色: string; 所属船舶: string }

const ENDPOINT = '/api/crewchange'
const columns = ['计划编号', '所属船舶', '登船人员', '离船人员', '登船人数', '离船人数', '登船时间', '离船时间', '提交人', '确认人', '确认时间', '计划状态']
const statuses = ['待确认', '已确认', '已取消']

const session = useSessionStore()
const accounts = ref<Account[]>([])
const currentOperator = ref('')
const rows = ref<Row[]>([])
const crew = ref<Row[]>([])
const expiredCrew = ref<Row[]>([])
const total = ref(0)
const notice = ref('')
const errorMessage = ref('')
const showForm = ref(false)
const filters = reactive({ keyword: '', vessel: '', status: '' })
const form = reactive({ vessel: '', boardTime: '', leaveTime: '', boarding: [] as string[], leaving: [] as string[] })

const vessels = computed(() => [...new Set(crew.value.map((member) => String(member.所属船舶)))] as string[])
const boardCandidates = computed(() => crew.value.filter((member) => member.所属船舶 === form.vessel && member.在船状态 === '已离船'))
const leaveCandidates = computed(() => crew.value.filter((member) => member.所属船舶 === form.vessel && member.在船状态 === '在船'))
const countMismatch = computed(() => form.boarding.length !== form.leaving.length)

const stats = computed(() => [
  { label: '待确认计划', value: rows.value.filter((row) => row.status === '待确认').length },
  { label: '已确认计划', value: rows.value.filter((row) => row.status === '已确认').length },
  { label: '在船人数', value: crew.value.filter((member) => member.在船状态 === '在船').length },
  { label: '证件过期', value: expiredCrew.value.length },
])

const accountHint = computed(() => {
  const account = accounts.value.find((item) => item.姓名 === currentOperator.value)
  if (!account) return ''
  if (account.角色 === '船员管理员') return '船员管理员可提交任意船舶的换班计划'
  if (account.角色 === '值班人员') return `值班人员只能提交「${account.所属船舶}」的换班计划`
  return '该角色只能查看，提交会被拒绝并说明原因'
})

function displayCell(row: Row, column: string) {
  if (column === '计划状态') return row.status ?? '—'
  const value = row[column]
  if (Array.isArray(value)) return value.join('、')
  return value ?? '—'
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function resetFilters() {
  filters.keyword = ''
  filters.vessel = ''
  filters.status = ''
  void reload()
}

function resetForm() {
  form.boarding = []
  form.leaving = []
  form.boardTime = ''
  form.leaveTime = ''
}

async function submitCreate() {
  notice.value = ''
  errorMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({
        values: {
          所属船舶: form.vessel,
          登船人员: form.boarding.join('、'),
          离船人员: form.leaving.join('、'),
          登船时间: form.boardTime.replace('T', ' '),
          离船时间: form.leaveTime.replace('T', ' '),
          提交人: currentOperator.value,
        },
      }),
    })
    const result = await response.json()
    if (!result.ok) {
      errorMessage.value = result.message || '换班计划提交被拒绝'
      return
    }
    notice.value = result.message || '换班计划已登记'
    resetForm()
    showForm.value = false
    await reloadAll()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '换班计划提交失败'
  }
}

async function runAction(action: string, row: Row) {
  notice.value = ''
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, 操作人: currentOperator.value } }),
    })
    const result = await response.json()
    if (!result.ok) {
      errorMessage.value = result.message || '换班动作未生效'
      return
    }
    notice.value = result.message || '换班动作已生效'
    await reloadAll()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '换班动作执行失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.keyword) query.set('keyword', filters.keyword)
  if (filters.vessel) query.set('vessel', filters.vessel)
  if (filters.status) query.set('status', filters.status)
  query.set('size', '200')
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('换班计划列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '换班计划列表读取失败'
  }
}

async function reloadCrew() {
  try {
    const [crewRes, expiredRes] = await Promise.all([
      request(`${ENDPOINT}/crew`),
      request(`${ENDPOINT}/expired`),
    ])
    if (crewRes.ok) crew.value = (await crewRes.json()).items ?? []
    if (expiredRes.ok) expiredCrew.value = (await expiredRes.json()).items ?? []
  } catch {
    // 名单读取失败不打断页面，列表区照常展示
  }
}

async function reloadAll() {
  await Promise.all([reload(), reloadCrew()])
}

watch(currentOperator, (name) => {
  if (name) session.setOperator(name)
})

watch(() => form.vessel, () => {
  form.boarding = []
  form.leaving = []
})

onMounted(async () => {
  try {
    const response = await request(`${ENDPOINT}/accounts`)
    if (response.ok) {
      accounts.value = (await response.json()).items ?? []
      if (accounts.value.length && !currentOperator.value) {
        currentOperator.value = accounts.value[0].姓名
      }
    }
  } catch {
    // 账号名册读取失败时仍可查看列表
  }
  await reloadAll()
  if (!form.vessel && vessels.value.length) form.vessel = vessels.value[0]
})
</script>

<style scoped>
.account-bar { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 12px; }
.account-hint { color: var(--muted); font-size: 12px; }
.create-panel, .expired-panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.panel-title { margin: 0 0 8px; font-size: 14px; }
.crew-title { margin-top: 16px; }
.create-grid { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.pick-grid { display: flex; gap: 12px; margin-bottom: 8px; }
.pick-box { flex: 1; border: 1px dashed var(--border); border-radius: 6px; padding: 8px 10px; display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.pick-item { display: flex; gap: 6px; align-items: center; }
.ok-text { color: #027a48; }
select, input { padding: 4px 6px; border: 1px solid var(--border); border-radius: 4px; }
</style>
