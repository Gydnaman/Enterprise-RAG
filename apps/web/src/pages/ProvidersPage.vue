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
  catch (cause) { error.value = cause instanceof ApiError ? cause.problem.detail : '无法读取模型与组件状态。' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="page-title-row"><div><div class="eyebrow muted-eyebrow">当前模型与组件</div><h1>模型与组件状态</h1><p class="page-subtitle">查看回答使用的演示组件，以及文档解析、OCR 和向量存储是否已接入。</p></div><span class="mode-pill"><i />演示模式 · MOCK</span></div>
  <div class="provider-intro"><div class="provider-orbit"><span>⬡</span><i /><i /></div><div><div class="eyebrow">当前演示配置</div><h2>回答由本地固定流程生成</h2><p>Stage A 不连接真实大模型、OCR 或向量数据库；内置样例负责演示检索和引用流程。</p></div></div>
  <div v-if="error" class="alert alert-error" role="alert">{{ error }} <button @click="load">重试</button></div>
  <div v-if="loading" class="loading-card"><span class="spinner" />正在读取当前组件状态…</div>
  <div v-else class="provider-grid"><article v-for="provider in providers" :key="provider.provider" class="provider-card"><div class="provider-card-top"><span class="provider-symbol">✳</span><span class="provider-health"><i />{{ provider.available ? '可用' : '不可用' }}</span></div><div class="eyebrow muted-eyebrow">演示回答组件</div><h3>{{ provider.profile }}</h3><p>{{ provider.statusMessage || '当前使用固定的 Mock 回答流程。' }}</p><div class="provider-flags"><span><i :class="provider.registered ? 'flag-on' : ''" />{{ provider.registered ? '已注册' : '未注册' }}</span><span><i :class="provider.selected ? 'flag-on' : ''" />{{ provider.selected ? '当前选中' : '未选中' }}</span><span><i class="flag-on" />模式：{{ provider.mode.toUpperCase() }}</span></div><div class="provider-card-foot"><span>当前状态</span><b>{{ provider.available ? '已启用' : '未启用' }}</b></div></article>
    <article class="provider-card provider-deferred"><div class="provider-card-top"><span class="provider-symbol deferred-symbol">◇</span><span class="status-chip chip-neutral">暂未接入</span></div><div class="eyebrow muted-eyebrow">后续可扩展组件</div><h3>文档解析 · OCR · 向量存储</h3><p>这些组件尚未连接；当前不会从上传文件读取内容，也不会访问外部服务。</p><div class="provider-card-foot"><span>后续阶段</span><b>未配置</b></div></article></div>
</template>
