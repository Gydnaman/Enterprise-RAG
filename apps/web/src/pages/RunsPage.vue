<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, ApiError } from '../api/client'
import type { Run } from '../api/generated/types.gen'

const runs = ref<Run[]>([])
const page = ref(1)
const total = ref(0)
const loading = ref(true)
const loadingMore = ref(false)
const error = ref('')
const PAGE_SIZE = 25
async function load() {
  loading.value = true; error.value = ''
  try {
    const result = await api.runs(1, PAGE_SIZE)
    runs.value = result.items
    page.value = result.page
    total.value = result.total
  }
  catch (cause) { error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取 Run。' }
  finally { loading.value = false }
}
async function loadMore() {
  if (loadingMore.value || runs.value.length >= total.value) return
  loadingMore.value = true; error.value = ''
  try {
    const result = await api.runs(page.value + 1, PAGE_SIZE)
    runs.value.push(...result.items)
    page.value = result.page
    total.value = result.total
  } catch (cause) { error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取更多 Run。' }
  finally { loadingMore.value = false }
}
function title(run: Run) { return ({ answer: 'Agent 问答', retrieval: '检索调试', upload: '文件上传', demo_trace: 'Demo 处理轨迹' } as Record<string, string>)[run.kind] }
function time(value: string) { return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value)) }
onMounted(load)
</script>

<template>
  <div class="page-title-row"><div><div class="eyebrow muted-eyebrow">RUN OBSERVABILITY</div><h1>运行记录</h1><p class="page-subtitle">每个操作都有持久事件、状态和安全错误码。</p></div><button class="button button-outline" @click="load">↻ 刷新</button></div>
  <div class="run-summary-strip"><div><span class="summary-icon">◷</span><span><b>{{ total }}</b><small>全部运行</small></span></div><div><span class="summary-icon summary-green">✓</span><span><b>{{ runs.filter(run => run.status === 'completed').length }}</b><small>当前页已完成</small></span></div><div><span class="summary-icon summary-amber">⌁</span><span><b>{{ runs.filter(run => run.status === 'running' || run.status === 'queued').length }}</b><small>当前页进行中</small></span></div><div class="mode-summary"><span class="mode-pill"><i /> DEMO / MOCK</span></div></div>
  <div v-if="error" class="alert alert-error" role="alert">{{ error }} <button @click="load">重试</button></div>
  <div v-if="loading" class="loading-card"><span class="spinner" /> 正在加载运行记录…</div>
  <div v-else-if="!runs.length" class="empty-card wide-empty"><div class="empty-icon">◷</div><h3>还没有运行记录</h3><p>检索、问答和 Demo 处理轨迹都会在这里留下可续传事件。</p><RouterLink class="button button-primary" to="/retrieval">运行一次检索 <span>→</span></RouterLink></div>
  <div v-else class="table-card runs-table">
    <div class="table-header"><span>运行 / 来源</span><span>创建时间</span><span>状态</span><span>结果</span><span /></div>
    <RouterLink v-for="run in runs" :key="run.id" :to="`/runs/${run.id}`" class="run-row">
      <span class="run-row-main"><b>{{ title(run) }}</b><small>{{ run.id }} · {{ String(run.subject.kind ?? run.kind).toUpperCase() }}</small></span>
      <span class="run-time">{{ time(run.createdAt) }}</span>
      <span class="run-status" :class="`state-${run.status}`"><i />{{ run.status }}</span>
      <span class="result-code">{{ run.safeErrorCode || run.resultStatus || '—' }}</span><span class="row-chevron">›</span>
    </RouterLink>
  </div>
  <div v-if="!loading && runs.length < total" class="load-more-row">
    <button class="button button-outline" :disabled="loadingMore" @click="loadMore">
      {{ loadingMore ? '正在加载…' : `加载更多（${runs.length} / ${total}）` }}
    </button>
  </div>
</template>
