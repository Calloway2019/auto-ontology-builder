import { createRouter, createWebHashHistory } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      component: DefaultLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/dashboard/DashboardView.vue'),
          meta: { title: '智能仪表盘', icon: 'DataBoard' },
        },
        {
          path: 'data/upload',
          name: 'DataUpload',
          component: () => import('@/views/data/DataUploadView.vue'),
          meta: { title: '数据管理', icon: 'FolderOpened' },
        },
        {
          path: 'ontology',
          name: 'OntologyList',
          component: () => import('@/views/ontology/OntologyListView.vue'),
          meta: { title: '本体管理', icon: 'Connection' },
        },
        {
          path: 'ontology/:id',
          name: 'OntologyDetail',
          component: () => import('@/views/ontology/OntologyDetailView.vue'),
          meta: { title: '本体详情', hidden: true },
        },
        {
          path: 'graph',
          name: 'Graph',
          component: () => import('@/views/graph/GraphView.vue'),
          meta: { title: '知识图谱', icon: 'Share' },
        },
        {
          path: 'chat',
          name: 'Chat',
          component: () => import('@/views/chat/ChatView.vue'),
          meta: { title: '智能问答', icon: 'ChatDotRound' },
        },
        {
          path: 'settings/llm',
          name: 'LLMConfig',
          component: () => import('@/views/settings/LLMConfigView.vue'),
          meta: { title: 'LLM 配置', icon: 'Setting', group: 'settings' },
        },
      ],
    },
  ],
})

export default router
