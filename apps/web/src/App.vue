<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => {
  if (route.path === '/') return '知识库总览'
  if (route.path.includes('/documents/')) return '文档与解析观察'
  if (route.path.startsWith('/retrieval')) return '检索调试'
  if (route.path.startsWith('/chat')) return 'Agent 问答'
  if (route.path.startsWith('/runs')) return '运行追踪'
  if (route.path.startsWith('/providers')) return 'Provider 状态'
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
        <RouterLink to="/" class="nav-link"><span class="nav-icon">▦</span>知识库</RouterLink>
        <RouterLink to="/retrieval" class="nav-link"><span class="nav-icon">⌕</span>检索调试</RouterLink>
        <RouterLink to="/chat" class="nav-link"><span class="nav-icon">✳</span>Agent 问答</RouterLink>
        <RouterLink to="/runs" class="nav-link"><span class="nav-icon">◷</span>运行记录</RouterLink>
        <RouterLink to="/providers" class="nav-link"><span class="nav-icon">⬡</span>Provider 状态</RouterLink>
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
          <span class="mode-pill"><i /> DEMO / MOCK</span>
          <a class="icon-button" href="/api/v1/openapi.json" target="_blank" rel="noreferrer" aria-label="查看 OpenAPI">↗</a>
          <div class="avatar top-avatar">D</div>
        </div>
      </header>
      <div class="page-wrap"><RouterView /></div>
    </main>
  </div>
</template>
