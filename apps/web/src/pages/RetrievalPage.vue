<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, ApiError, IdempotencyKeyManager } from '../api/client'
import type { Document, Evidence, KnowledgeBase } from '../api/generated/types.gen'

const route = useRoute()
const bases = ref<KnowledgeBase[]>([])
const documents = ref<Document[]>([])
const selectedIds = ref<string[]>([])
const knowledgeBaseId = ref(String(route.query.kb ?? ''))
const query = ref('')
const evidence = ref<Evidence[]>([])
const runId = ref('')
const loading = ref(true)
const searching = ref(false)
const searched = ref(false)
const error = ref('')
const fixtures = computed(() => documents.value.filter(doc => doc.isFixture && doc.status === 'ready'))
let documentRequest = 0
let searchGeneration = 0
const retrievalKeys = new IdempotencyKeyManager()

async function load() {
  loading.value = true
  error.value = ''
  try {
    bases.value = (await api.knowledgeBases()).items
    if (!knowledgeBaseId.value || !bases.value.some(kb => kb.id === knowledgeBaseId.value)) knowledgeBaseId.value = bases.value[0]?.id ?? ''
    await loadDocuments()
  } catch (cause) { error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取知识库。' }
  finally { loading.value = false }
}
async function loadDocuments() {
  const requestId = ++documentRequest
  const selectedBaseId = knowledgeBaseId.value
  documents.value = []
  if (!selectedBaseId) return
  try {
    const result = await api.documents(selectedBaseId)
    if (requestId === documentRequest && selectedBaseId === knowledgeBaseId.value) documents.value = result.items
  } catch (cause) {
    if (requestId === documentRequest && selectedBaseId === knowledgeBaseId.value) {
      documents.value = []
      error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取知识库文档。'
    }
  }
}
async function search() {
  if (searching.value || !query.value.trim() || !knowledgeBaseId.value) return
  const requestedBase = knowledgeBaseId.value
  const requestQuery = query.value
  const requestDocumentIds = [...selectedIds.value]
  const generation = ++searchGeneration
  searching.value = true
  error.value = ''
  const identity = `retrieval:${JSON.stringify([requestedBase, requestQuery, requestDocumentIds])}`
  try {
    const key = await retrievalKeys.keyFor(identity)
    const result = await api.retrieve(requestedBase, requestQuery, requestDocumentIds, key)
    await retrievalKeys.complete(identity, key)
    if (generation === searchGeneration && requestedBase === knowledgeBaseId.value) {
      evidence.value = result.evidence
      runId.value = result.runId
      searched.value = true
    }
  } catch (cause) {
    if (generation === searchGeneration && requestedBase === knowledgeBaseId.value) {
      error.value = cause instanceof ApiError ? cause.problem.detail : '检索失败。'
    }
  } finally {
    if (generation === searchGeneration) searching.value = false
  }
}
function toggle(id: string) { selectedIds.value = selectedIds.value.includes(id) ? selectedIds.value.filter(value => value !== id) : [...selectedIds.value, id] }
onMounted(load)
watch(knowledgeBaseId, async () => {
  selectedIds.value = []
  evidence.value = []
  runId.value = ''
  searched.value = false
  error.value = ''
  searchGeneration++
  searching.value = false
  await loadDocuments()
})
</script>

<template>
  <div class="page-title-row"><div><div class="eyebrow muted-eyebrow">RETRIEVAL PLAYGROUND</div><h1>检索调试</h1><p class="page-subtitle">用只读 Fixture 探索 Evidence 来源。分数仅用于演示，不代表检索质量。</p></div><span class="mode-pill"><i /> DEMO / MOCK</span></div>
  <div class="debug-layout">
    <section class="debug-panel">
      <div class="panel-title"><div class="panel-step">01</div><div><h2>检索输入</h2><p>选择资料范围并提交一个问题</p></div></div>
      <div class="field"><label for="kb-select">知识库</label><select id="kb-select" v-model="knowledgeBaseId" :disabled="loading"><option v-for="kb in bases" :key="kb.id" :value="kb.id">{{ kb.name }}</option></select></div>
      <div class="field"><div class="field-label-row"><label>文档过滤 <span>可选</span></label><button class="text-button" @click="selectedIds = []">清空</button></div><div v-if="fixtures.length" class="filter-list"><label v-for="doc in fixtures" :key="doc.id" class="filter-option"><input type="checkbox" :checked="selectedIds.includes(doc.id)" @change="toggle(doc.id)" /><span class="custom-check">✓</span><span>{{ doc.filename }}<small>READY FIXTURE</small></span></label></div><div v-else class="inline-empty">当前知识库没有可检索的 Fixture。</div></div>
      <div class="field"><label for="retrieval-query">查询内容</label><textarea id="retrieval-query" v-model="query" maxlength="4000" rows="5" placeholder="例如：上传文件是否会自动解析？" @keydown.ctrl.enter="search" /><small class="field-help">{{ query.length }} / 4000 · Ctrl + Enter 运行</small></div>
      <button class="button button-primary full-button" :disabled="searching || loading || !query.trim() || !knowledgeBaseId" @click="search">{{ searching ? '正在检索…' : '运行检索' }} <span>→</span></button>
      <div v-if="error" class="alert alert-error" role="alert">{{ error }}</div>
    </section>

    <section class="results-panel">
      <div class="results-heading"><div><div class="eyebrow muted-eyebrow">RETRIEVAL RESULT</div><h2>{{ searched ? `${evidence.length} 条 Evidence` : '等待检索' }}</h2></div><RouterLink v-if="runId" :to="`/runs/${runId}`" class="run-link">Run {{ runId.slice(0, 8) }} <span>↗</span></RouterLink></div>
      <div v-if="loading" class="result-placeholder"><span class="spinner" />连接工作台 API…</div>
      <div v-else-if="!searched" class="result-placeholder"><div class="placeholder-orbit"><span>⌕</span></div><b>输入一个问题开始调试</b><p>Evidence 将附带原始 Revision 与 Chunk 身份。</p></div>
      <div v-else-if="!evidence.length" class="no-evidence"><div class="no-evidence-mark">—</div><div class="eyebrow muted-eyebrow">NO EVIDENCE</div><h3>当前知识库中没有找到可引用的资料。</h3><p>演示回答会明确说明资料不足，不会生成 Citation。</p></div>
      <div v-else class="evidence-list">
        <article v-for="item in evidence" :key="item.chunkId" class="evidence-card">
          <div class="evidence-card-top"><span class="rank-label">EVIDENCE {{ String(item.rank).padStart(2, '0') }}</span><span class="score-label">{{ item.score.toFixed(3) }} <small>MOCK SCORE</small></span></div>
          <p class="evidence-snippet">{{ item.snippet }}</p>
          <div class="evidence-path"><span>{{ item.filename }}</span><span>·</span><span>{{ item.headingPath.join(' / ') }}</span><span v-if="item.page">· Page {{ item.page }}</span></div>
          <div class="evidence-footer"><code>{{ item.revisionId }} / {{ item.chunkId }}</code><RouterLink :to="`/documents/${item.documentId}/chunks`">定位来源 <span>↗</span></RouterLink></div>
          <span class="evidence-mode">DEMO / MOCK</span>
        </article>
      </div>
    </section>
  </div>
</template>
