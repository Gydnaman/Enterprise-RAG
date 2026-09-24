<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, ApiError, IdempotencyKeyManager, uploadIdempotencyIdentity } from '../api/client'
import type { Document, KnowledgeBase, Run } from '../api/generated/types.gen'

const route = useRoute()
const kb = ref<KnowledgeBase | null>(null)
const documents = ref<Document[]>([])
const runs = ref<Run[]>([])
const documentTotal = ref(0)
const documentPage = ref(1)
const loading = ref(true)
const loadingMore = ref(false)
const busyId = ref('')
const error = ref('')
const notice = ref('')
const selectedFile = ref<File | null>(null)
const kbId = computed(() => String(route.params.id))
const DOCUMENT_PAGE_SIZE = 25
const uploadKeys = new IdempotencyKeyManager()
const processKeys = new IdempotencyKeyManager()
let loadGeneration = 0

function traceFor(documentId: string, attempt: number) {
  return runs.value.find(run => run.kind === 'demo_trace'
    && run.subject.kind === 'demo_trace'
    && run.subject.documentId === documentId
    && run.subject.attemptNumber === attempt)
}
function canProcess(doc: Document) { return (doc.id === 'fixture-doc-handbook' || doc.status === 'uploaded_unprocessed') && !traceFor(doc.id, 1) }
function canRetry(doc: Document) { return traceFor(doc.id, 1)?.status === 'failed' && !traceFor(doc.id, 2) }

async function loadDemoTraceRuns(selectedKb: string) {
  if (!selectedKb) return []
  const filters = { knowledgeBaseId: selectedKb, kind: 'demo_trace' }
  const firstPage = await api.runs(1, 100, filters)
  const allRuns = [...firstPage.items]
  let page = firstPage.page
  let total = firstPage.total
  while (allRuns.length < total) {
    const next = await api.runs(++page, 100, filters)
    allRuns.push(...next.items)
    total = next.total
    if (!next.items.length) break
  }
  return allRuns
}

async function load() {
  const generation = ++loadGeneration
  const requestedKb = kbId.value
  kb.value = null
  documents.value = []
  runs.value = []
  documentPage.value = 1
  documentTotal.value = 0
  selectedFile.value = null
  busyId.value = ''
  loadingMore.value = false
  loading.value = true
  error.value = ''
  try {
    const [base, docs, demoRuns] = await Promise.all([
      api.knowledgeBases(),
      api.documents(requestedKb, 1, DOCUMENT_PAGE_SIZE),
      loadDemoTraceRuns(requestedKb),
    ])
    if (generation !== loadGeneration || requestedKb !== kbId.value) return
    kb.value = base.items.find(item => item.id === requestedKb) ?? null
    documents.value = docs.items
    documentPage.value = docs.page
    documentTotal.value = docs.total
    runs.value = demoRuns
  } catch (cause) {
    if (generation === loadGeneration && requestedKb === kbId.value) {
      error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取文档。'
    }
  } finally {
    if (generation === loadGeneration && requestedKb === kbId.value) loading.value = false
  }
}

async function loadMoreDocuments() {
  if (loadingMore.value || documents.value.length >= documentTotal.value) return
  const requestedKb = kbId.value
  loadingMore.value = true
  error.value = ''
  try {
    const next = await api.documents(requestedKb, documentPage.value + 1, DOCUMENT_PAGE_SIZE)
    if (requestedKb === kbId.value) {
      documents.value.push(...next.items)
      documentPage.value = next.page
      documentTotal.value = next.total
    }
  } catch (cause) {
    if (requestedKb === kbId.value) error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取更多文档。'
  } finally { if (requestedKb === kbId.value) loadingMore.value = false }
}

async function upload() {
  if (!selectedFile.value) return
  const file = selectedFile.value
  const requestedKb = kbId.value
  busyId.value = 'upload'
  error.value = ''
  notice.value = ''
  try {
    const identity = await uploadIdempotencyIdentity(requestedKb, file)
    const key = await uploadKeys.keyFor(identity)
    const result = await api.upload(requestedKb, file, key)
    if (!('document' in result)) {
      if (requestedKb === kbId.value) {
        notice.value = '上传仍在安全保存流程中；再次提交同一文件会使用原请求键继续处理。'
        await load()
      }
      return
    }
    await uploadKeys.complete(identity, key)
    if (requestedKb === kbId.value) notice.value = `文件已安全保存为“${result.document.status}”，尚未解析。`
    if (selectedFile.value === file) {
      selectedFile.value = null
      const input = document.getElementById('upload-file') as HTMLInputElement | null
      if (input) input.value = ''
    }
    if (requestedKb === kbId.value) await load()
  } catch (cause) {
    if (requestedKb === kbId.value) error.value = cause instanceof ApiError ? `${cause.problem.title}：${cause.problem.detail}` : '上传失败。'
  }
  finally { if (requestedKb === kbId.value) busyId.value = '' }
}

async function startTrace(doc: Document, retry = false) {
  const requestedKb = kbId.value
  const identity = `process:${doc.id}:${retry ? 'retry' : 'start'}`
  busyId.value = doc.id
  error.value = ''
  notice.value = ''
  try {
    const key = await processKeys.keyFor(identity)
    const result = await api.process(doc.id, retry, key)
    await processKeys.complete(identity, key)
    if (requestedKb === kbId.value) {
      notice.value = `已创建 DEMO / MOCK Run ${result.run.id.slice(0, 8)}。文件内容不会被解析。`
      await load()
    }
  } catch (cause) {
    if (requestedKb === kbId.value) error.value = cause instanceof ApiError ? cause.problem.detail : '无法启动 Demo 轨迹。'
  } finally { if (requestedKb === kbId.value) busyId.value = '' }
}

function statusLabel(status: string) {
  return ({ ready: 'Fixture 已就绪', uploaded_unprocessed: '已保存 · 尚未解析', upload_pending: '上传处理中', upload_failed: '上传失败' } as Record<string, string>)[status] ?? status
}
function formatBytes(value: number) { return value < 1024 ? `${value} B` : `${(value / 1024 / 1024).toFixed(1)} MB` }
onMounted(load)
watch(kbId, () => { notice.value = ''; void load() })
</script>

<template>
  <div class="page-title-row">
    <div><div class="eyebrow muted-eyebrow">KNOWLEDGE BASE / DOCUMENTS</div><h1>{{ kb?.name || '文档管理' }}</h1><p class="page-subtitle">浏览只读 Fixture、上传文件，并检查未解析状态与 Demo Run。</p></div>
    <RouterLink to="/" class="button button-outline">← 返回知识库</RouterLink>
  </div>
  <div class="truth-banner"><span class="truth-icon">i</span><div><b>Stage A 上传只保存文件与元数据</b><p>上传文件不会提取文本、生成 Chunk 或参与检索。Demo Run 仅展示状态轨迹。</p></div><span class="status-chip chip-blue">DEMO / MOCK</span></div>
  <div v-if="error" class="alert alert-error" role="alert">{{ error }} <button @click="load">重试</button></div>
  <div v-if="notice" class="alert alert-success" role="status">{{ notice }}</div>
  <section class="upload-card">
    <div class="upload-heading"><div class="upload-icon">↑</div><div><h2>上传文档</h2><p>PDF、DOCX、Markdown 或 TXT · 最大 25 MiB</p></div><span class="upload-lock">只保存 · 不解析</span></div>
    <div class="upload-controls"><label class="file-picker" for="upload-file"><span class="file-plus">＋</span><span><b>{{ selectedFile?.name || '选择一个文件' }}</b><small>{{ selectedFile ? formatBytes(selectedFile.size) : '校验格式签名后安全保存到本地' }}</small></span><em>浏览文件</em></label><input id="upload-file" type="file" accept=".pdf,.docx,.md,.txt" @change="selectedFile = ($event.target as HTMLInputElement).files?.[0] ?? null" /><button class="button button-primary" :disabled="!selectedFile || busyId === 'upload'" @click="upload">{{ busyId === 'upload' ? '上传中…' : '安全上传' }} <span>→</span></button></div>
  </section>

  <section class="section-heading compact-heading"><div><div class="eyebrow muted-eyebrow">SOURCE MATERIAL</div><h2>文档 <span class="count-badge">{{ documentTotal }}</span></h2></div><span class="quiet-meta">按最近添加排序</span></section>
  <div v-if="loading" class="loading-card"><span class="spinner" /> 正在读取文档…</div>
  <div v-else-if="!documents.length" class="empty-card wide-empty"><div class="empty-icon">▤</div><h3>当前知识库没有文档</h3><p>选择一个 PDF、DOCX、Markdown 或 TXT 文件开始演示安全上传。</p></div>
  <div v-else class="document-list">
    <article v-for="doc in documents" :key="doc.id" class="document-card">
      <div class="document-icon" :class="doc.isFixture ? 'doc-fixture' : 'doc-upload'">{{ doc.mediaType.includes('pdf') ? 'PDF' : doc.mediaType.includes('word') ? 'DOC' : 'TXT' }}</div>
      <div class="document-main"><div class="document-name-row"><h3>{{ doc.filename }}</h3><span v-if="doc.isFixture" class="status-chip chip-blue">READ ONLY FIXTURE</span></div><p>{{ formatBytes(doc.sizeBytes) }} <span>·</span> Revision 1 <span>·</span> {{ doc.id.slice(0, 8) }}</p><div class="document-status" :class="doc.status === 'ready' ? 'status-ready' : 'status-unprocessed'"><i />{{ statusLabel(doc.status) }}</div></div>
      <div class="document-actions"><RouterLink :to="`/documents/${doc.id}/chunks`" class="button button-outline button-small">查看 Chunks <span>↗</span></RouterLink><button v-if="canProcess(doc)" class="button button-soft button-small" :disabled="busyId === doc.id" @click="startTrace(doc)">{{ busyId === doc.id ? '排队中…' : '运行 Demo 轨迹' }}</button><button v-else-if="canRetry(doc)" class="button button-soft button-small" :disabled="busyId === doc.id" @click="startTrace(doc, true)">{{ busyId === doc.id ? '排队中…' : '重试轨迹' }}</button><span v-else-if="doc.isFixture && doc.id !== 'fixture-doc-handbook'" class="quiet-meta">只读内容</span><span v-else-if="doc.status === 'uploaded_unprocessed'" class="quiet-meta">等待 Demo Run 完成</span></div>
    </article>
  </div>
  <div v-if="!loading && documents.length < documentTotal" class="load-more-row">
    <button class="button button-outline" :disabled="loadingMore" @click="loadMoreDocuments">
      {{ loadingMore ? '正在加载…' : `加载更多（${documents.length} / ${documentTotal}）` }}
    </button>
  </div>
</template>
