<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '../api/client'
import type { ProviderStatus } from '../api/generated/types.gen'
const providers = ref<ProviderStatus[]>([])
const loading = ref(true)
const error = ref('')
async function load() {
  loading.value = true; error.value = ''
  try { providers.value = await api.providers() }
  catch (cause) { error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取 Provider 状态。' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-title-row"><div><div class="eyebrow muted-eyebrow">SERVER-SIDE ADAPTER REGISTRY</div><h1>Provider 状态</h1><p class="page-subtitle">查看服务端已注册并选中的适配器配置，不返回凭据或内部异常。</p></div><span class="mode-pill"><i /> STAGE A MOCK</span></div>
  <div class="provider-intro"><div class="provider-orbit"><span>⬡</span><i /><i /></div><div><div class="eyebrow">ADAPTER PROFILE</div><h2>所有演示能力都在本地运行</h2><p>Stage A 不连接真实 LLM、OCR 或向量数据库。Mock profile 在启动时验证并保持固定。</p></div></div>
  <div v-if="error" class="alert alert-error" role="alert">{{ error }} <button @click="load">重试</button></div>
  <div v-if="loading" class="loading-card"><span class="spinner" />读取服务端 Provider registry…</div>
  <div v-else class="provider-grid"><article v-for="provider in providers" :key="provider.provider" class="provider-card"><div class="provider-card-top"><span class="provider-symbol">✳</span><span class="provider-health"><i />{{ provider.available ? 'AVAILABLE' : 'UNAVAILABLE' }}</span></div><div class="eyebrow muted-eyebrow">{{ provider.provider }}</div><h3>{{ provider.profile }}</h3><p>{{ provider.statusMessage || 'Mock adapter status is available.' }}</p><div class="provider-flags"><span><i :class="provider.registered ? 'flag-on' : ''" />已注册</span><span><i :class="provider.selected ? 'flag-on' : ''" />当前选中</span><span><i class="flag-on" />MODE: {{ provider.mode.toUpperCase() }}</span></div><div class="provider-card-foot"><span>服务端配置</span><b>ACTIVE</b></div></article>
    <article class="provider-card provider-deferred"><div class="provider-card-top"><span class="provider-symbol deferred-symbol">◇</span><span class="status-chip chip-neutral">DEFERRED</span></div><div class="eyebrow muted-eyebrow">FUTURE ADAPTER PORTS</div><h3>Parser · OCR · Vector Store</h3><p>未来可通过已定义的稳定端口接入。当前不会读取用户文件或访问外部服务。</p><div class="provider-card-foot"><span>Stage B</span><b>NOT CONFIGURED</b></div></article></div>
</template>
