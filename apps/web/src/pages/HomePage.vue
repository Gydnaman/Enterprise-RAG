<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
const apiState = ref<'checking' | 'connected' | 'disconnected' | 'error'>('checking')

const demoKnowledgeBaseId = computed(() => knowledgeBases.value.find(kb => kb.id.startsWith('fixture'))?.id ?? '')
const demoDocumentsPath = computed(() => demoKnowledgeBaseId.value
  ? `/knowledge-bases/${demoKnowledgeBaseId.value}/documents`
  : '')
const demoRetrievalPath = computed(() => demoKnowledgeBaseId.value
  ? { path: '/retrieval', query: { kb: demoKnowledgeBaseId.value } }
  : '/retrieval')
const demoChatPath = computed(() => demoKnowledgeBaseId.value
  ? { path: '/chat', query: { kb: demoKnowledgeBaseId.value } }
  : '/chat')

async function load() {
  loading.value = true
  error.value = ''
  apiState.value = 'checking'
  try {
    const [kbResult, runResult] = await Promise.all([api.knowledgeBases(), api.runs(1, 5)])
    knowledgeBases.value = kbResult.items
    runs.value = runResult.items.slice(0, 5)
    apiState.value = 'connected'
  } catch (cause) {
    apiState.value = cause instanceof ApiError ? 'error' : 'disconnected'
    error.value = cause instanceof ApiError
      ? `API 有响应，但无法读取工作台数据：${cause.problem.detail}`
      : '无法连接 API。请确认服务已启动，然后重试。'
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
    error.value = cause instanceof ApiError ? cause.problem.detail : '创建知识库失败。请稍后重试。'
  } finally { saving.value = false }
}

function shortTime(value: string) { return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) }
function focusCreate() { document.getElementById('kb-name')?.focus() }
function runStatusLabel(status: string) {
  return ({ queued: '排队中', running: '运行中', completed: '已完成', failed: '失败' } as Record<string, string>)[status] ?? status
}
onMounted(load)
</script>

<template>
  <section class="home-welcome" aria-labelledby="welcome-title">
    <div class="home-welcome-copy">
      <div class="eyebrow"><span class="eyebrow-dot" /> 新手从这里开始</div>
      <h1 id="welcome-title">用内置样例走一遍<br /><em>知识问答全流程</em></h1>
      <p>不用配置模型或准备文件。按下面三步，查看资料、检索证据，再检查答案引用。</p>
    </div>
    <aside class="home-environment" aria-label="当前环境状态">
      <div class="environment-demo">
        <span class="environment-mark" aria-hidden="true">D</span>
        <span><b>本地演示环境</b><small>Stage A · 只读样例 + Mock 流程</small></span>
      </div>
      <div class="environment-api" :class="`api-${apiState}`" role="status" aria-live="polite">
        <i aria-hidden="true" />
        <span>{{ apiState === 'checking' ? '正在检查 API…' : apiState === 'connected' ? 'API 已连接，可以开始体验' : apiState === 'error' ? 'API 有响应，但读取失败' : 'API 未连接，请先启动服务' }}</span>
      </div>
      <p>上传文件只会保存，不会自动解析；回答来自内置样例。</p>
    </aside>
  </section>

  <div v-if="error" class="alert alert-error home-error" role="alert">
    {{ error }} <button @click="load">重新连接</button>
  </div>

  <section class="onboarding-section" aria-labelledby="onboarding-title">
    <div class="onboarding-heading">
      <div><div class="eyebrow muted-eyebrow">三步完成第一次体验</div><h2 id="onboarding-title">从资料到可追溯的回答</h2></div>
      <span class="onboarding-hint">每一步都可以回到来源查看</span>
    </div>
    <div class="onboarding-grid">
      <article class="onboarding-step">
        <span class="step-number">01</span>
        <div class="step-copy"><h3>先看示例资料</h3><p>打开内置文档，看看资料如何整理成章节和文本片段。</p></div>
        <RouterLink v-if="demoDocumentsPath" class="step-action" :to="demoDocumentsPath">打开 Demo 文档 <span aria-hidden="true">→</span></RouterLink>
        <span v-else class="step-action step-action-disabled">{{ loading ? '正在载入样例…' : '暂无可用样例' }}</span>
      </article>
      <article class="onboarding-step">
        <span class="step-number">02</span>
        <div class="step-copy"><h3>检索相关证据</h3><p>尝试一个问题，查看系统找到的资料片段及其来源。</p></div>
        <RouterLink class="step-action" :to="demoRetrievalPath">试试检索 <span aria-hidden="true">→</span></RouterLink>
      </article>
      <article class="onboarding-step">
        <span class="step-number">03</span>
        <div class="step-copy"><h3>检查回答引用</h3><p>向演示 Agent 提问，再从 Citation 跳回原始 Chunk。</p></div>
        <RouterLink class="step-action" :to="demoChatPath">开始问答 <span aria-hidden="true">→</span></RouterLink>
      </article>
    </div>
  </section>

  <section class="section-heading home-section-heading">
    <div><div class="eyebrow muted-eyebrow">你的资料空间</div><h2>知识库 <span class="count-badge">{{ knowledgeBases.length }}</span></h2></div>
    <button class="button button-outline" @click="focusCreate"><span aria-hidden="true">＋</span>新建知识库</button>
  </section>

  <div v-if="loading" class="loading-card"><span class="spinner" /> 正在读取知识库…</div>
  <div v-else class="kb-grid">
    <article v-for="(kb, index) in knowledgeBases" :key="kb.id" class="kb-card">
      <div class="kb-card-top"><div class="kb-icon" :class="`kb-color-${index % 4}`" aria-hidden="true">▦</div><span class="status-chip" :class="kb.id.startsWith('fixture') ? 'chip-blue' : 'chip-green'">{{ kb.id.startsWith('fixture') ? '内置样例' : '自建' }}</span></div>
      <h3>{{ kb.name }}</h3><p class="kb-description">{{ kb.description || '暂无描述' }}</p>
      <div class="kb-card-meta"><span>{{ kb.id.startsWith('fixture') ? '只读演示资料' : '本地资料空间' }}</span><span>{{ shortTime(kb.updatedAt) }}</span></div>
      <div class="kb-card-actions"><RouterLink :to="`/knowledge-bases/${kb.id}/documents`">查看文档 <span aria-hidden="true">→</span></RouterLink><RouterLink :to="{ path: '/chat', query: { kb: kb.id } }" class="text-link">问答 <span aria-hidden="true">↗</span></RouterLink></div>
    </article>
    <div v-if="!knowledgeBases.length && !loading" class="empty-card"><div class="empty-icon" aria-hidden="true">▦</div><h3>还没有知识库</h3><p>创建一个资料空间，或确认 API 已启动后重新连接。</p><button class="button button-soft" @click="load">重新连接</button></div>
    <form class="kb-create-card" @submit.prevent="create">
      <div class="create-card-heading"><div class="plus-ring" aria-hidden="true">＋</div><div><b>新建知识库</b><small>创建独立的资料空间</small></div></div>
      <p class="create-stage-note">当前版本可以创建资料空间；上传文件只会保存，暂不会解析或加入检索。</p>
      <label for="kb-name">名称</label><input id="kb-name" v-model.trim="name" maxlength="120" placeholder="例如：产品手册" required />
      <label for="kb-description">描述 <small>可选</small></label><textarea id="kb-description" v-model="description" maxlength="2000" rows="2" placeholder="这组资料用于…" />
      <button class="button button-primary create-submit" :disabled="saving || !name.trim()">{{ saving ? '正在创建…' : '创建知识库' }} <span aria-hidden="true">→</span></button>
    </form>
  </div>

  <section class="section-heading runs-heading"><div><div class="eyebrow muted-eyebrow">操作记录</div><h2>最近运行</h2></div><RouterLink class="text-link" to="/runs">查看全部 <span aria-hidden="true">→</span></RouterLink></section>
  <div class="table-card">
    <div v-if="!runs.length" class="table-empty">还没有运行记录。可以先试一次检索，或打开示例文档启动 Demo 处理轨迹。</div>
    <RouterLink v-for="run in runs" :key="run.id" :to="`/runs/${run.id}`" class="run-row">
      <span class="run-kind-icon" :class="`run-${run.kind}`" aria-hidden="true">{{ run.kind === 'answer' ? '✳' : run.kind === 'retrieval' ? '⌕' : run.kind === 'upload' ? '↑' : '◷' }}</span>
      <span class="run-row-main"><b>{{ run.kind === 'answer' ? 'Agent 问答' : run.kind === 'retrieval' ? '检索调试' : run.kind === 'upload' ? '文件上传' : 'Demo 处理轨迹' }}</b><small>{{ run.id.slice(0, 8) }} · {{ run.mode.toUpperCase() }}</small></span>
      <span class="run-time">{{ shortTime(run.createdAt) }}</span>
      <span class="run-status" :class="`state-${run.status}`"><i aria-hidden="true" />{{ runStatusLabel(run.status) }}</span><span class="row-chevron" aria-hidden="true">›</span>
    </RouterLink>
  </div>
</template>
