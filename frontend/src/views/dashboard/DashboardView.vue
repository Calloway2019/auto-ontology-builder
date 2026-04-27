<template>
  <div class="dashboard-page">
    <div class="dashboard-header">
      <h3>智能仪表盘</h3>
      <el-button type="primary" @click="showEditor = true" :disabled="!projectId">
        + 添加模块
      </el-button>
    </div>

    <!-- Module Grid -->
    <div class="module-grid" v-if="modules.length > 0">
      <div
        v-for="mod in modules"
        :key="mod.id"
        class="module-card"
        :class="`size-${mod.size || 'medium'}`"
      >
        <el-card shadow="hover">
          <template #header>
            <div class="module-header">
              <span class="module-title">{{ mod.title }}</span>
              <div class="module-actions">
                <el-button size="small" link @click="handleRefresh(mod.id)" :loading="mod.status === 'loading'">
                  <el-icon><Refresh /></el-icon>
                </el-button>
                <el-button size="small" link type="danger" @click="handleDelete(mod.id)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </template>

          <!-- Module Content -->
          <div class="module-content" v-loading="mod.status === 'loading'">
            <template v-if="mod.last_result">
              <!-- Structured: Table -->
              <div v-if="mod.last_result.type === 'structured' && mod.last_result.structured">
                <el-table
                  :data="mod.last_result.structured.rows?.slice(0, 10)"
                  size="small"
                  border
                  max-height="300"
                >
                  <el-table-column
                    v-for="col in mod.last_result.structured.columns"
                    :key="col.key"
                    :prop="col.key"
                    :label="col.title"
                  />
                </el-table>
              </div>
              <!-- Text -->
              <div v-else-if="mod.last_result.text" class="module-text" v-html="renderMd(mod.last_result.text)" />
              <!-- Empty -->
              <el-empty v-else description="暂无数据" :image-size="60" />
            </template>
            <el-empty v-else description="点击刷新获取结果" :image-size="60" />
          </div>

          <div class="module-footer" v-if="mod.last_updated">
            <span class="update-time">更新于 {{ formatTime(mod.last_updated) }}</span>
          </div>
        </el-card>
      </div>
    </div>

    <el-empty v-else description="暂无分析模块，点击上方按钮添加" />

    <!-- Add Module Dialog -->
    <el-dialog v-model="showEditor" title="添加分析模块" width="500px">
      <el-form :model="newModule" label-width="100px">
        <el-form-item label="模块标题">
          <el-input v-model="newModule.title" placeholder="如：关键风险器件Top10" />
        </el-form-item>
        <el-form-item label="分析问题">
          <el-input
            v-model="newModule.question"
            type="textarea"
            rows="4"
            placeholder="输入要分析的问题，如：列出风险最高的10个关键器件及其风险原因"
          />
        </el-form-item>
        <el-form-item label="预设模板">
          <el-select v-model="selectedTemplate" placeholder="选择预设问题" @change="applyTemplate" clearable>
            <el-option label="关键风险器件 Top10" value="risk_top10" />
            <el-option label="一周内预计可齐套产品" value="kit_week" />
            <el-option label="供应商集中度分析" value="supplier" />
            <el-option label="物料替代方案推荐" value="alternative" />
          </el-select>
        </el-form-item>
        <el-form-item label="展示方式">
          <el-radio-group v-model="newModule.display_type">
            <el-radio value="table">表格</el-radio>
            <el-radio value="text">文本</el-radio>
            <el-radio value="bar">柱状图</el-radio>
            <el-radio value="list">列表</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="模块大小">
          <el-radio-group v-model="newModule.size">
            <el-radio value="small">小</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="large">大</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditor = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listModules, createModule, deleteModule, refreshModule } from '@/api/dashboard'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt()

const projectId = inject<any>('currentProjectId')
const modules = ref<any[]>([])
const showEditor = ref(false)
const selectedTemplate = ref('')
const newModule = ref({
  title: '',
  question: '',
  display_type: 'table',
  size: 'medium',
})

const templates: Record<string, { title: string; question: string }> = {
  risk_top10: {
    title: '关键风险器件Top10',
    question: '基于知识图谱，列出风险最高的10个关键器件，包括名称、风险等级和风险原因',
  },
  kit_week: {
    title: '一周内预计可齐套产品',
    question: '分析知识图谱中的产品和物料库存，列出一周内预计可以齐套的产品及其完成度',
  },
  supplier: {
    title: '供应商集中度分析',
    question: '分析各供应商供应的物料数量和占比，识别供应商集中度过高的风险点',
  },
  alternative: {
    title: '物料替代方案推荐',
    question: '识别当前库存不足的物料，推荐可能的替代方案或替代物料',
  },
}

function applyTemplate(val: string) {
  if (val && templates[val]) {
    newModule.value.title = templates[val].title
    newModule.value.question = templates[val].question
  }
}

function renderMd(text: string) {
  return md.render(text)
}

function formatTime(t: string) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN')
}

async function loadModules() {
  if (!projectId?.value) return
  try {
    const res = await listModules(projectId.value)
    modules.value = res.data || []
  } catch (e) {
    // ignore
  }
}

async function handleCreate() {
  if (!newModule.value.title || !newModule.value.question) {
    ElMessage.warning('请填写标题和分析问题')
    return
  }
  try {
    await createModule({
      project_id: projectId.value,
      ...newModule.value,
    })
    showEditor.value = false
    newModule.value = { title: '', question: '', display_type: 'table', size: 'medium' }
    selectedTemplate.value = ''
    ElMessage.success('模块创建成功')
    loadModules()
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  }
}

async function handleRefresh(moduleId: string) {
  try {
    await refreshModule(moduleId)
    ElMessage.info('正在刷新...')
    // Poll for result
    setTimeout(() => loadModules(), 3000)
    setTimeout(() => loadModules(), 8000)
    setTimeout(() => loadModules(), 15000)
  } catch (e: any) {
    ElMessage.error(e.message || '刷新失败')
  }
}

async function handleDelete(moduleId: string) {
  await ElMessageBox.confirm('确定删除此模块？', '提示', { type: 'warning' })
  await deleteModule(moduleId)
  ElMessage.success('已删除')
  loadModules()
}

watch(() => projectId?.value, () => loadModules())
onMounted(() => loadModules())
</script>

<style scoped>
.dashboard-page {
  max-width: 1400px;
}
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.module-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}
.module-card.size-large {
  grid-column: 1 / -1;
}
.module-card.size-small {
  min-width: 300px;
}
.module-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.module-title {
  font-weight: 600;
}
.module-actions {
  display: flex;
  gap: 4px;
}
.module-content {
  min-height: 100px;
}
.module-text {
  line-height: 1.6;
  font-size: 14px;
}
.module-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.module-text :deep(th),
.module-text :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 6px 12px;
  text-align: left;
}
.module-text :deep(th) {
  background: #f5f7fa;
}
.module-footer {
  margin-top: 8px;
  text-align: right;
}
.update-time {
  font-size: 12px;
  color: #909399;
}
</style>
