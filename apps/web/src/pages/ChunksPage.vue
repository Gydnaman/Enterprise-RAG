<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api, ApiError } from '../api/client'
import type { DocumentDetail, ChunkTree } from '../api/generated/types.gen'

const route = useRoute()
const id = computed(() => String(route.params.id))
const detail = ref<DocumentDetail | null>(null)
const tree = ref<ChunkTree | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try { [detail.value, tree.value] = await Promise.all([api.document(id.value), api.chunks(id.value)]) }
  catch (cause) { error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取 Chunk 数据。' }
  finally { loading.value = false }
}
onMounted(load)
watch(id, load)
</script>

<template>
  <div class="page-title-row">
    <div><div class="eyebrow muted-eyebrow">DOCUMENT / CHUNK INSPECTOR</div><h1>Chunk 观测</h1><p class="page-subtitle">查看 Section → Chunk 的来源层级、页码与标题路径。</p></div>
    <RouterLink v-if="detail" :to="`/knowledge-bases/${detail.document.knowledgeBaseId}/documents`" class="button button-outline">← 返回文档</RouterLink>
  </div>
  <div v-if="detail" class="source-summary"><div class="document-icon" :class="detail.document.isFixture ? 'doc-fixture' : 'doc-upload'">{{ detail.document.mediaType.includes('pdf') ? 'PDF' : detail.document.mediaType.includes('word') ? 'DOC' : 'TXT' }}</div><div><b>{{ detail.document.filename }}</b><small>{{ detail.currentRevision.id }} · Revision {{ detail.currentRevision.revisionNumber }}</small></div><span class="status-chip" :class="detail.document.isFixture ? 'chip-blue' : 'chip-amber'">{{ detail.document.isFixture ? 'DEMO FIXTURE' : '尚未解析' }}</span></div>
  <div v-if="error" class="alert alert-error" role="alert">{{ error }} <button @click="load">重试</button></div>
  <div v-if="loading" class="loading-card"><span class="spinner" /> 正在载入 Chunk 树…</div>
  <template v-else-if="tree">
    <div class="inspector-toolbar"><span><b>{{ tree.sections.length }}</b> 个 Section <i /> <b>{{ tree.sections.reduce((sum, section) => sum + section.chunks.length, 0) }}</b> 个 Chunk</span><span class="mode-pill"><i /> DEMO / MOCK</span></div>
    <div v-if="!tree.sections.length" class="empty-card wide-empty no-chunks"><div class="empty-icon">⌗</div><h3>暂无解析结果</h3><p>该用户文件只做了安全保存。Stage A 不会把上传内容变成 Section、Chunk 或检索证据。</p><RouterLink :to="`/knowledge-bases/${detail?.document.knowledgeBaseId}/documents`" class="text-link">返回文档管理 <span>→</span></RouterLink></div>
    <div v-else class="section-stack">
      <article v-for="section in tree.sections" :key="section.id" class="section-card">
        <div class="section-card-head"><div class="section-number">{{ String(section.order).padStart(2, '0') }}</div><div><div class="eyebrow muted-eyebrow">SECTION · {{ section.pageStart ? `PAGE ${section.pageStart}${section.pageEnd && section.pageEnd !== section.pageStart ? `–${section.pageEnd}` : ''}` : 'NO PAGE' }}</div><h2>{{ section.title }}</h2><div class="heading-path">{{ section.headingPath.join(' / ') }}</div></div><span class="count-badge">{{ section.chunks.length }} chunks</span></div>
        <div class="chunk-stack"><div v-for="chunk in section.chunks" :key="chunk.id" class="chunk-row"><div class="chunk-order">CHUNK {{ String(chunk.order).padStart(2, '0') }}</div><div class="chunk-copy"><p>{{ chunk.text }}</p><div class="chunk-meta"><code>{{ chunk.id }}</code><span v-if="chunk.pageStart">Page {{ chunk.pageStart }}</span><span v-if="chunk.startOffset !== null">Offset {{ chunk.startOffset }}–{{ chunk.endOffset }}</span></div></div><span class="chunk-source-check">✓</span></div></div>
      </article>
    </div>
  </template>
</template>
