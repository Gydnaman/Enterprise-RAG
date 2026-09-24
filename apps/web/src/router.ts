import { createRouter, createWebHistory } from 'vue-router'
import HomePage from './pages/HomePage.vue'
import DocumentsPage from './pages/DocumentsPage.vue'
import ChunksPage from './pages/ChunksPage.vue'
import RetrievalPage from './pages/RetrievalPage.vue'
import ChatPage from './pages/ChatPage.vue'
import RunsPage from './pages/RunsPage.vue'
import RunDetailPage from './pages/RunDetailPage.vue'
import ProvidersPage from './pages/ProvidersPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomePage },
    { path: '/knowledge-bases/:id/documents', component: DocumentsPage },
    { path: '/documents/:id/chunks', component: ChunksPage },
    { path: '/retrieval', component: RetrievalPage },
    { path: '/chat', component: ChatPage },
    { path: '/runs', component: RunsPage },
    { path: '/runs/:id', component: RunDetailPage },
    { path: '/providers', component: ProvidersPage },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
