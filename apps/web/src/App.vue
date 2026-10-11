<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => {
  if (route.path === '/') return '知识库总览'
  if (route.path.includes('/documents/')) return '文档与片段'
  if (route.path.startsWith('/retrieval')) return '检索调试'
  if (route.path.startsWith('/chat')) return 'Agent 问答'
  if (route.path.startsWith('/runs')) return '运行追踪'
  if (route.path.startsWith('/providers')) return '模型与组件状态'
  return '企业知识工作台'
})
</script>

<template>
  <div class="app-frame">
    <aside class="sidebar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">知</span>
        <span class="brand-copy"><strong>知引</strong><small>企业知识工作台</small></span>
      </RouterLink>
      <div class="workspace-label">工作空间 <span>LOCAL</span></div>
      <nav class="main-nav" aria-label="主导航">
        <p class="nav-group-label">开始体验</p>
        <RouterLink to="/" class="nav-link" aria-label="知识库总览" title="知识库总览">
          <svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></svg>
          <span>知识库总览</span>
        </RouterLink>
        <p class="nav-group-label nav-group-secondary">RAG 体验</p>
        <RouterLink to="/retrieval" class="nav-link" aria-label="检索调试" title="检索调试">
          <svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.5 4.5" /></svg>
          <span>检索调试</span>
        </RouterLink>
        <RouterLink to="/chat" class="nav-link" aria-label="Agent 问答" title="Agent 问答">
          <svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11.2a7.7 7.7 0 0 1-8 7.5 8.8 8.8 0 0 1-3.6-.8L4 19l1.2-3.3A7.2 7.2 0 0 1 4 11.2a7.7 7.7 0 0 1 8-7.5 7.7 7.7 0 0 1 8 7.5Z" /><path d="M8.5 11.5h.01M12 11.5h.01M15.5 11.5h.01" /></svg>
          <span>Agent 问答</span>
        </RouterLink>
        <p class="nav-group-label nav-group-secondary">查看运行情况</p>
        <RouterLink to="/runs" class="nav-link" aria-label="运行记录" title="运行记录">
          <svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></svg>
          <span>运行记录</span>
        </RouterLink>
        <RouterLink to="/providers" class="nav-link" aria-label="模型与组件状态" title="模型与组件状态">
          <svg class="nav-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.5 20 8v8l-8 4.5L4 16V8l8-4.5Z" /><path d="M8.5 12h7M12 8.5v7" /></svg>
          <span>模型与组件</span>
        </RouterLink>
      </nav>
      <div class="sidebar-bottom">
        <div class="profile-mini"><div class="avatar">D</div><div><b>演示工作区</b><small>本地单用户模式</small></div><span class="online-dot" /></div>
        <p class="sidebar-footnote">Stage A · 本地演示<br />没有连接外部模型或向量库</p>
      </div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div class="breadcrumbs"><span>工作台</span><span class="crumb-chevron">/</span><strong>{{ title }}</strong></div>
        <div class="top-actions">
          <span class="mode-pill" title="当前使用内置样例和固定演示流程，没有连接真实模型"><i aria-hidden="true" />演示模式 · MOCK</span>
          <a class="icon-button" href="/api/v1/openapi.json" target="_blank" rel="noreferrer" aria-label="查看 OpenAPI">↗</a>
          <div class="avatar top-avatar">D</div>
        </div>
      </header>
      <div class="page-wrap"><RouterView /></div>
    </main>
  </div>
</template>
