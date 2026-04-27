<template>
  <el-container class="layout-container">
    <!-- Sidebar -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="layout-aside">
      <div class="logo-area" @click="isCollapse = !isCollapse">
        <el-icon :size="24"><Share /></el-icon>
        <span v-if="!isCollapse" class="logo-text">Ontology Builder</span>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :router="true"
        background-color="#1d1e2c"
        text-color="#a3a6b4"
        active-text-color="#409eff"
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <template #title>智能仪表盘</template>
        </el-menu-item>

        <el-menu-item index="/data/upload">
          <el-icon><FolderOpened /></el-icon>
          <template #title>数据管理</template>
        </el-menu-item>

        <el-menu-item index="/ontology">
          <el-icon><Connection /></el-icon>
          <template #title>本体管理</template>
        </el-menu-item>

        <el-menu-item index="/graph">
          <el-icon><Share /></el-icon>
          <template #title>知识图谱</template>
        </el-menu-item>

        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>智能问答</template>
        </el-menu-item>

        <el-sub-menu index="settings">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统设置</span>
          </template>
          <el-menu-item index="/settings/llm">LLM 配置</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <!-- Main Content -->
    <el-container>
      <el-header class="layout-header">
        <div class="header-left">
          <span class="page-title">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <el-select
            v-model="currentProjectId"
            placeholder="选择项目"
            size="default"
            style="width: 200px"
            @change="onProjectChange"
          >
            <el-option
              v-for="p in projects"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
          <el-button
            type="primary"
            :icon="Plus"
            circle
            size="small"
            style="margin-left: 8px"
            @click="showCreateDialog = true"
          />
          <el-button
            type="danger"
            :icon="Delete"
            circle
            size="small"
            style="margin-left: 4px"
            @click="handleDeleteProject"
            :disabled="!currentProjectId"
          />
        </div>
      </el-header>

      <el-main class="layout-main">
        <router-view :key="currentProjectId" />
      </el-main>
    </el-container>

    <!-- Create Project Dialog -->
    <el-dialog v-model="showCreateDialog" title="新建项目" width="460px" :close-on-click-modal="false">
      <el-form :model="newProject" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="newProject.name" placeholder="请输入项目名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="newProject.description" type="textarea" :rows="3" placeholder="可选：简要描述项目内容" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="doCreateProject" :loading="creating" :disabled="!newProject.name.trim()">
          创建
        </el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, provide } from 'vue'
import { useRoute } from 'vue-router'
import { Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listProjects, createProject, deleteProject } from '@/api/ontology'

const route = useRoute()
const isCollapse = ref(false)
const projects = ref<any[]>([])
const currentProjectId = ref('')

const showCreateDialog = ref(false)
const creating = ref(false)
const newProject = ref({ name: '', description: '' })

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => {
  const meta = route.meta as any
  return meta?.title || 'Ontology Builder'
})

// Provide project ID and refresh function to all child components
provide('currentProjectId', currentProjectId)
provide('refreshProjects', loadProjects)

async function loadProjects() {
  try {
    const res = await listProjects()
    projects.value = res.data || []
    if (projects.value.length > 0 && !currentProjectId.value) {
      currentProjectId.value = projects.value[0].id
    }
  } catch (e) {
    // ignore
  }
}

function onProjectChange(val: string) {
  currentProjectId.value = val
}

async function doCreateProject() {
  if (!newProject.value.name.trim()) return
  creating.value = true
  try {
    const res = await createProject({
      name: newProject.value.name.trim(),
      description: newProject.value.description.trim(),
    })
    showCreateDialog.value = false
    newProject.value = { name: '', description: '' }
    ElMessage.success('项目创建成功')
    await loadProjects()
    if (res.data?.id) {
      currentProjectId.value = res.data.id
    }
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleDeleteProject() {
  if (!currentProjectId.value) return
  const currentName = projects.value.find((p: any) => p.id === currentProjectId.value)?.name || '当前项目'
  try {
    await ElMessageBox.confirm(
      `确定要删除项目「${currentName}」吗？删除后项目下所有数据（数据源、本体、问答记录等）将不可恢复。`,
      '删除项目',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteProject(currentProjectId.value)
    ElMessage.success('项目已删除')
    currentProjectId.value = ''
    await loadProjects()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.layout-aside {
  background: #1d1e2c;
  transition: width 0.3s;
  overflow: hidden;
}

.logo-area {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  border-bottom: 1px solid #2d2e3e;
}

.logo-text {
  white-space: nowrap;
  overflow: hidden;
}

.sidebar-menu {
  border-right: none;
}

.layout-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 60px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
}

.layout-main {
  background: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}
</style>
