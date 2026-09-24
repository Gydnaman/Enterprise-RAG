<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, ApiError } from '../api/client'
import type { KnowledgeBase, Run } from '../api/generated/types.gen'

const knowledgeBases = ref<KnowledgeBase[]>([])
const runs = ref<Run[]>([])
const name = ref('')
const description = ref('')
const loading = ref(true)
const saving = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [kbResult, runResult] = await Promise.all([api.knowledgeBases(), api.runs(1, 5)])
    knowledgeBases.value = kbResult.items
    runs.value = runResult.items.slice(0, 5)
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.problem.detail : '无法连接 API。请先启动本地服务。'
  } finally { loading.value = false }
}

async function create() {
  if (!name.value.trim()) return
  saving.value = true
  error.value = ''
  try {
    await api.createKnowledgeBase(name.value, description.value || undefined)
    name.value = ''
    description.value = ''
    await load()
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.problem.detail : '创建知识库失败。'
  } finally { saving.value = false }
}

function shortTime(value: string) { return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) }
function focusCreate() { document.getElementById('kb-name')?.focus() }
onMounted(load)
</script>

<template>
  <section class="hero-panel">
    <div class="hero-copy">
      <div class="eyebrow"><span class="eyebrow-dot" /> KNOWLEDGE OPERATIONS</div>
      <h1>让每一条回答<br /><em>都有据可循。</em></h1>
      <p>从知识库到引用证据，清晰观察每个阶段的输入、输出与运行轨迹。</p>
      <div class="hero-actions">
        <RouterLink class="button button-primary" to="/retrieval"><span>⌕</span>开始检索调试</RouterLink>
        <RouterLink class="button button-quiet" to="/chat">打开 Agent 问答 <span>→</span></RouterLink>
      </div>
    </div>
    <div class="hero-art" aria-hidden="true">
      <div class="orbit orbit-one" /><div class="orbit orbit-two" />
      <div class="art-card art-back"><div class="art-lines"><i /><i /><i /></div></div>
      <div class="art-card art-front"><span class="art-badge">EVIDENCE</span><div class="art-quote">“每条引用都能<br />回到原始 Chunk。”</div><div class="art-source"><span class="source-dot" /> fixture · page 02</div></div>
      <span class="art-spark spark-one">✦</span><span class="art-spark spark-two">✧</span>
    </div>
    <div class="hero-foot"><span>本工作台当前展示只读 Fixture 与确定性 Mock 流程</span><span>STAGE A <b>·</b> LOCAL DEMO</span></div>
  </section>

  <section class="section-heading">
    <div><div class="eyebrow muted-eyebrow">YOUR KNOWLEDGE SPACE</div><h2>知识库 <span class="count-badge">{{ knowledgeBases.length }}</span></h2></div>
    <button class="button button-outline" @click="focusCreate"><span>＋</span>新建知识库</button>
  </section>

  <div v-if="error" class="alert alert-error" role="alert">{{ error }} <button @click="load">重试</button></div>
  <div v-if="loading" class="loading-card"><span class="spinner" /> 正在读取知识库…</div>
  <div v-else class="kb-grid">
    <article v-for="(kb, index) in knowledgeBases" :key="kb.id" class="kb-card">
      <div class="kb-card-top"><div class="kb-icon" :class="`kb-color-${index % 4}`">▦</div><span class="status-chip" :class="kb.id.startsWith('fixture_') || kb.id.startsWith('fixture-') ? 'chip-blue' : 'chip-green'">{{ kb.id.startsWith('fixture') ? 'FIXTURE' : 'ACTIVE' }}</span></div>
      <h3>{{ kb.name }}</h3><p class="kb-description">{{ kb.description || '暂无描述' }}</p>
      <div class="kb-card-meta"><span><i class="tiny-dot" /> API 已连接</span><span>{{ shortTime(kb.updatedAt) }}</span></div>
      <div class="kb-card-actions"><RouterLink :to="`/knowledge-bases/${kb.id}/documents`">查看文档 <span>→</span></RouterLink><RouterLink :to="{ path: '/chat', query: { kb: kb.id } }" class="text-link">问答 <span>↗</span></RouterLink></div>
    </article>
    <div v-if="!knowledgeBases.length && !loading" class="empty-card"><div class="empty-icon">▦</div><h3>还没有知识库</h3><p>创建一个知识库，然后上传演示文件或查看只读 Fixture。</p></div>
    <form class="kb-create-card" @submit.prevent="create">
      <div class="create-card-heading"><div class="plus-ring">＋</div><div><b>新建知识库</b><small>创建独立的资料空间</small></div></div>
      <label for="kb-name">名称</label><input id="kb-name" v-model="name" maxlength="120" placeholder="例如：产品手册" required />
      <label for="kb-description">描述 <small>可选</small></label><textarea id="kb-description" v-model="description" maxlength="2000" rows="2" placeholder="这组资料用于…" />
      <button class="button button-primary create-submit" :disabled="saving || !name.trim()">{{ saving ? '创建中…' : '创建知识库' }} <span>→</span></button>
    </form>
  </div>

  <section class="section-heading runs-heading"><div><div class="eyebrow muted-eyebrow">OBSERVABILITY</div><h2>最近运行</h2></div><RouterLink class="text-link" to="/runs">查看全部 <span>→</span></RouterLink></section>
  <div class="table-card">
    <div v-if="!runs.length" class="table-empty">还没有运行记录。试试检索或启动 Demo 处理轨迹。</div>
    <RouterLink v-for="run in runs" :key="run.id" :to="`/runs/${run.id}`" class="run-row">
      <span class="run-kind-icon" :class="`run-${run.kind}`">{{ run.kind === 'answer' ? '✳' : run.kind === 'retrieval' ? '⌕' : run.kind === 'upload' ? '↑' : '◷' }}</span>
      <span class="run-row-main"><b>{{ run.kind === 'answer' ? 'Agent 问答' : run.kind === 'retrieval' ? '检索调试' : run.kind === 'upload' ? '文件上传' : 'Demo 处理轨迹' }}</b><small>{{ run.id.slice(0, 8) }} · {{ run.mode.toUpperCase() }}</small></span>
      <span class="run-time">{{ shortTime(run.createdAt) }}</span>
      <span class="run-status" :class="`state-${run.status}`"><i />{{ run.status }}</span><span class="row-chevron">›</span>
    </RouterLink>
  </div>
</template>
