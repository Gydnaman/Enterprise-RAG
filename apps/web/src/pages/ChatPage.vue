<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api, ApiError, eventFrom, IdempotencyKeyManager } from '../api/client'
import type { Citation, Conversation, KnowledgeBase, Message, Run } from '../api/generated/types.gen'

const route = useRoute()
const router = useRouter()
const bases = ref<KnowledgeBase[]>([])
const knowledgeBaseId = ref(String(route.query.kb ?? ''))
const conversation = ref<Conversation | null>(null)
const messages = ref<Message[]>([])
const question = ref('')
const loading = ref(true)
const sending = ref(false)
const reconnecting = ref(false)
const error = ref('')
const activeRun = ref<Run | null>(null)
const sendKeys = new IdempotencyKeyManager()
let source: EventSource | null = null
const activeAnswer = computed(() => messages.value.find(message => message.runId === activeRun.value?.id && message.role === 'assistant'))

async function load() {
  loading.value = true
  error.value = ''
  try {
    bases.value = (await api.knowledgeBases()).items
    if (!knowledgeBaseId.value || !bases.value.some(kb => kb.id === knowledgeBaseId.value)) knowledgeBaseId.value = bases.value[0]?.id ?? ''
    const sessionId = String(route.query.session ?? '')
    if (sessionId) await openConversation(sessionId)
  } catch (cause) { error.value = cause instanceof ApiError ? cause.problem.detail : '无法连接问答 API。' }
  finally { loading.value = false }
}

async function openConversation(id: string) {
  const result = await api.conversation(id)
  conversation.value = result.conversation
  messages.value = result.messages
  knowledgeBaseId.value = result.conversation.knowledgeBaseId
  if (result.activeRunId) {
    const activeMessages = result.messages.filter(message => message.runId === result.activeRunId)
    const activeAssistant = activeMessages.find(message => message.role === 'assistant')
    if (activeAssistant) {
      activeAssistant.content = ''
      activeAssistant.citations = []
      activeAssistant.status = 'queued'
    }
    activeRun.value = {
      id: result.activeRunId,
      kind: 'answer',
      status: 'running',
      mode: 'mock',
      subject: {
        kind: 'answer',
        knowledgeBaseId: result.conversation.knowledgeBaseId,
        conversationId: result.conversation.id,
        userMessageId: activeMessages.find(message => message.role === 'user')?.id ?? '',
        assistantMessageId: activeMessages.find(message => message.role === 'assistant')?.id ?? '',
      },
      createdAt: '',
      startedAt: null,
      finishedAt: null,
      resultStatus: null,
      safeErrorCode: null,
    }
    connect(result.activeRunId)
  }
}

async function newConversation() {
  if (!knowledgeBaseId.value) return
  stopStream()
  try {
    conversation.value = await api.createConversation(knowledgeBaseId.value)
    messages.value = []
    activeRun.value = null
    await router.replace({ query: { ...route.query, kb: knowledgeBaseId.value, session: conversation.value.id } })
  } catch (cause) { error.value = cause instanceof ApiError ? cause.problem.detail : '无法创建会话。' }
}

async function send() {
  if (!conversation.value || !question.value.trim() || sending.value || activeRun.value) return
  sending.value = true
  error.value = ''
  const prompt = question.value.trim()
  const identity = `answer:${conversation.value.id}:${prompt}`
  question.value = ''
  try {
    const key = await sendKeys.keyFor(identity)
    const result = await api.sendMessage(conversation.value.id, prompt, key)
    await sendKeys.complete(identity, key)
    messages.value.push(result.userMessage, result.assistantMessage)
    activeRun.value = result.run
    connect(result.run.id)
  } catch (cause) {
    question.value = prompt
    error.value = cause instanceof ApiError ? cause.problem.detail : '提交问题失败。'
  } finally { sending.value = false }
}

function connect(runId: string) {
  stopStream()
  source = new EventSource(api.streamUrl(runId))
  source.onopen = () => { reconnecting.value = false }
  source.onerror = () => { reconnecting.value = true }
  for (const type of ['answer_delta', 'citation_added', 'phase_updated', 'run_started', 'run_completed', 'run_failed']) {
    source.addEventListener(type, raw => {
      const event = eventFrom(raw as MessageEvent<string>)
      if (!event) return
      const assistant = messages.value.find(item => item.runId === runId && item.role === 'assistant')
      if (!assistant) return
      if (event.eventType === 'answer_delta') {
        assistant.status = 'streaming'
        assistant.content += String(event.payload.text ?? '')
      } else if (event.eventType === 'citation_added') {
        const citation: Citation = {
          revisionId: String(event.payload.revisionId ?? ''), chunkId: String(event.payload.chunkId ?? ''),
          page: typeof event.payload.page === 'number' ? event.payload.page : null, quote: String(event.payload.quote ?? ''),
        }
        if (!assistant.citations.some(item => item.chunkId === citation.chunkId)) assistant.citations.push(citation)
      } else if (event.eventType === 'run_completed') {
        assistant.status = 'completed'
        activeRun.value = null
        source?.close()
        source = null
      } else if (event.eventType === 'run_failed') {
        assistant.status = 'failed'
        assistant.content = ''
        assistant.citations = []
        activeRun.value = null
        source?.close()
        source = null
      }
    })
  }
}

function stopStream() { source?.close(); source = null; reconnecting.value = false }
function quickQuestion(value: string) { question.value = value }
onMounted(load)
onUnmounted(stopStream)
watch(knowledgeBaseId, () => { if (!conversation.value || conversation.value.knowledgeBaseId !== knowledgeBaseId.value) { messages.value = []; conversation.value = null; activeRun.value = null } })
</script>

<template>
  <div class="page-title-row"><div><div class="eyebrow muted-eyebrow">GROUNDED ANSWERS</div><h1>Agent 问答</h1><p class="page-subtitle">答案只基于可追溯的 Fixture Evidence。无证据时会明确说明资料不足。</p></div><span class="mode-pill"><i /> DEMO / MOCK</span></div>
  <div class="chat-workspace">
    <aside class="chat-context">
      <div class="chat-context-head"><div class="mini-agent">✳</div><div><b>Knowledge Agent</b><small>Fixture-backed · Mock flow</small></div></div>
      <div class="field"><label for="chat-kb">知识库</label><select id="chat-kb" v-model="knowledgeBaseId" :disabled="loading || Boolean(activeRun)"><option v-for="kb in bases" :key="kb.id" :value="kb.id">{{ kb.name }}</option></select></div>
      <button class="button button-outline full-button" :disabled="!knowledgeBaseId || Boolean(activeRun)" @click="newConversation">＋ 新建会话</button>
      <div class="context-divider" />
      <div class="eyebrow muted-eyebrow">示例问题</div>
      <button class="suggestion" @click="quickQuestion('上传的文件会自动解析并进入检索吗？')">上传的文件会自动解析并进入检索吗？ <span>↗</span></button>
      <button class="suggestion" @click="quickQuestion('Evidence 和 Citation 如何回到来源？')">Evidence 和 Citation 如何回到来源？ <span>↗</span></button>
      <div class="context-note"><b>真实边界</b><p>用户上传在 Stage A 只会安全保存。回答和引用均来自内置只读 Fixture。</p></div>
    </aside>

    <section class="chat-panel">
      <div class="chat-panel-head"><div><b>{{ conversation ? '演示问答会话' : '开始一个演示会话' }}</b><small>{{ conversation ? `Session ${conversation.id.slice(0, 8)}` : '选择知识库并创建会话' }}</small></div><span v-if="reconnecting" class="reconnect-status"><i /> 正在恢复事件流…</span><span v-else class="connection-status"><i /> 持久事件流</span></div>
      <div class="chat-messages" aria-live="polite">
        <div v-if="loading" class="chat-welcome"><span class="spinner" /> 正在加载…</div>
        <div v-else-if="!conversation" class="chat-welcome"><div class="welcome-agent">✳</div><h2>从资料证据开始对话</h2><p>创建会话后，Agent 会先检索只读演示资料，再生成带来源的回答。</p><button class="button button-primary" :disabled="!knowledgeBaseId" @click="newConversation">创建问答会话 <span>→</span></button></div>
        <template v-else>
          <div class="system-note"><span>⌁</span> 回答模式为 DEMO / MOCK · 浏览器断线后会从持久事件继续</div>
          <article v-for="message in messages" :key="message.id" class="message-row" :class="`message-${message.role}`">
            <div class="message-avatar">{{ message.role === 'assistant' ? '✳' : 'D' }}</div>
            <div class="message-body"><div class="message-meta"><b>{{ message.role === 'assistant' ? 'Knowledge Agent' : '你' }}</b><span v-if="message.role === 'assistant'" class="status-chip chip-blue">DEMO / MOCK</span><RouterLink v-if="message.runId" :to="`/runs/${message.runId}`" class="message-run-link">Run ↗</RouterLink></div>
              <p v-if="message.status === 'queued' && !message.content" class="thinking"><i /> 正在运行演示流程…</p>
              <p v-else-if="message.status === 'failed'" class="failed-answer">运行失败。可在 Run 详情查看安全错误码。</p>
              <p v-else class="message-content">{{ message.content }}<span v-if="message.status === 'streaming'" class="typing-cursor" /></p>
              <div v-if="message.citations.length" class="citation-list"><div class="citation-heading">来源引用 <span>{{ message.citations.length }}</span></div><div v-for="citation in message.citations" :key="citation.chunkId" class="citation-item"><span class="citation-mark">↳</span><div><p>{{ citation.quote }}</p><RouterLink :to="`/documents/${citation.chunkId.includes('citation') ? 'fixture-doc-citation' : 'fixture-doc-handbook'}/chunks`">{{ citation.revisionId }} / {{ citation.chunkId }}<span v-if="citation.page"> · Page {{ citation.page }}</span> ↗</RouterLink></div></div></div>
            </div>
          </article>
        </template>
      </div>
      <form class="chat-composer" @submit.prevent="send"><textarea v-model="question" :disabled="!conversation || Boolean(activeRun)" rows="2" maxlength="4000" placeholder="向演示知识库提问…" @keydown.enter.exact.prevent="send" /><div class="composer-footer"><span>Enter 发送 · Shift + Enter 换行 <span class="composer-mode">DEMO / MOCK</span></span><button class="send-button" :disabled="!conversation || !question.trim() || sending || Boolean(activeRun)" aria-label="发送问题">{{ sending ? '…' : '↑' }}</button></div></form>
      <div v-if="error" class="alert alert-error chat-error" role="alert">{{ error }}</div>
    </section>
  </div>
</template>
