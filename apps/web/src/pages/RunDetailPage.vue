<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, ApiError, eventFrom } from '../api/client'
import type { Run, RunEvent } from '../api/generated/types.gen'

const route = useRoute()
const run = ref<Run | null>(null)
const events = ref<RunEvent[]>([])
const loading = ref(true)
const error = ref('')
const reconnecting = ref(false)
let source: EventSource | null = null
let loadGeneration = 0
const runId = () => String(route.params.id)

async function load() {
  const generation = ++loadGeneration
  const requestedId = runId()
  stop()
  run.value = null
  events.value = []
  reconnecting.value = false
  loading.value = true; error.value = ''
  try {
    const snapshot = await api.run(requestedId)
    if (generation !== loadGeneration || requestedId !== runId()) return
    run.value = snapshot.run
    events.value = snapshot.events
    if (snapshot.run.status === 'queued' || snapshot.run.status === 'running') connect(snapshot.run.id)
  } catch (cause) {
    if (generation === loadGeneration && requestedId === runId()) {
      error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取 Run 详情。'
    }
  } finally {
    if (generation === loadGeneration && requestedId === runId()) loading.value = false
  }
}
function connect(id: string) {
  source = new EventSource(api.streamUrl(id))
  source.onopen = () => { if (runId() === id) reconnecting.value = false }
  source.onerror = () => { if (runId() === id) reconnecting.value = true }
  for (const type of ['run_started', 'phase_updated', 'answer_delta', 'citation_added', 'upload_completed', 'retrieval_completed', 'run_completed', 'run_failed']) {
    source.addEventListener(type, raw => {
      if (runId() !== id) return
      const value = eventFrom(raw as MessageEvent<string>)
      if (!value || events.value.some(event => event.sequence === value.sequence)) return
      events.value.push(value)
      events.value.sort((a, b) => a.sequence - b.sequence)
      if (value.eventType === 'run_completed' || value.eventType === 'run_failed') {
        if (run.value) run.value.status = value.eventType === 'run_completed' ? 'completed' : 'failed'
        source?.close(); source = null
        void refreshRun(id)
      }
    })
  }
}
async function refreshRun(id: string) {
  try {
    const updated = (await api.run(id)).run
    if (runId() === id) run.value = updated
  } catch { /* Existing event timeline remains visible. */ }
}
function stop() { source?.close(); source = null }
function eventSummary(value: RunEvent) {
  if (value.eventType === 'answer_delta') return `答案增量：${String(value.payload.text ?? '')}`
  if (value.eventType === 'citation_added') return `加入来源引用 ${String(value.payload.chunkId ?? '')}`
  if (value.eventType === 'retrieval_completed') return `检索完成，找到 ${String(value.payload.evidenceCount ?? 0)} 条 DEMO Evidence`
  if (value.eventType === 'run_failed') return `安全错误码：${String(value.payload.safeErrorCode ?? 'internal_error')}`
  if (value.eventType === 'run_completed') return `运行完成 · ${String(value.payload.resultStatus ?? 'completed')}`
  if (value.eventType === 'upload_completed') return `文件已保存 ${String(value.payload.storedBytes ?? 0)} bytes · 尚未解析`
  return String(value.payload.summary ?? value.phase)
}
function time(value: string) { return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 2 }).format(new Date(value)) }
onMounted(load)
onUnmounted(stop)
watch(() => route.params.id, load)
</script>

<template>
  <div class="page-title-row"><div><div class="eyebrow muted-eyebrow">RUN DETAIL / EVENT REPLAY</div><h1>运行详情</h1><p class="page-subtitle">持久事件按确认序号回放；事件仅包含安全阶段摘要与来源身份。</p></div><RouterLink to="/runs" class="button button-outline">← 返回运行列表</RouterLink></div>
  <div v-if="error" class="alert alert-error" role="alert">{{ error }} <button @click="load">重试</button></div>
  <div v-if="loading" class="loading-card"><span class="spinner" /> 载入 Run 快照…</div>
  <template v-else-if="run">
    <section class="run-detail-hero"><div class="run-kind-icon" :class="`run-${run.kind}`">{{ run.kind === 'answer' ? '✳' : run.kind === 'retrieval' ? '⌕' : run.kind === 'upload' ? '↑' : '◷' }}</div><div class="run-detail-name"><div class="eyebrow muted-eyebrow">{{ run.kind.replace('_', ' ').toUpperCase() }} · {{ run.mode.toUpperCase() }}</div><h2>{{ run.id }}</h2><p>创建于 {{ new Date(run.createdAt).toLocaleString('zh-CN') }}</p></div><span class="run-status" :class="`state-${run.status}`"><i />{{ run.status }}</span><span v-if="reconnecting" class="reconnect-status"><i />恢复中</span><span class="result-chip">{{ run.resultStatus || run.safeErrorCode || 'IN PROGRESS' }}</span></section>
    <div class="run-detail-grid"><section class="detail-card"><div class="detail-card-head"><div><div class="eyebrow muted-eyebrow">PERSISTED EVENT LOG</div><h2>时间线 <span class="count-badge">{{ events.length }}</span></h2></div><span class="quiet-meta">exclusive cursor · {{ events.length ? events[events.length - 1].sequence : 0 }}</span></div>
      <div v-if="!events.length" class="inline-empty">尚未收到事件。连接保持打开并等待新的持久事件。</div>
      <div v-else class="timeline"> <article v-for="event in events" :key="event.sequence" class="timeline-item"><div class="timeline-pin" :class="event.eventType === 'run_failed' ? 'pin-error' : event.eventType === 'run_completed' ? 'pin-done' : ''"><i /></div><div class="timeline-content"><div class="timeline-meta"><b>{{ event.eventType.replaceAll('_', ' ') }}</b><code>#{{ String(event.sequence).padStart(3, '0') }}</code><time>{{ time(event.timestamp) }}</time></div><p>{{ eventSummary(event) }}</p><div class="timeline-foot"><span>{{ event.phase }}</span><span>{{ event.status }}</span></div></div></article></div>
    </section>
    <aside class="detail-aside"><div class="detail-card"><div class="eyebrow muted-eyebrow">RUN SUBJECT</div><h3>来源身份</h3><dl class="subject-list"><template v-for="(value, key) in run.subject" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></template></dl></div><div class="truth-card"><span class="truth-icon">i</span><div><b>DEMO / MOCK</b><p>此运行展示确定性的模拟轨迹，不代表真实解析或检索效果。</p></div></div></aside></div>
  </template>
</template>
