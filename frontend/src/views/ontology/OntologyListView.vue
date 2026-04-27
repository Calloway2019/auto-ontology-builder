<template>
  <div class="ontology-list-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>本体管理</span>
          <div>
            <el-button @click="showBuildLog = true" :disabled="!projectId || versions.length === 0">
              <el-icon><Document /></el-icon> 构建记录
            </el-button>
            <el-button type="primary" @click="handleBuild" :loading="building" :disabled="!projectId">
              构建本体
            </el-button>
          </div>
        </div>
      </template>

      <!-- Build Progress: 4-Stage Pipeline -->
      <div v-if="buildStatus.status && buildStatus.status !== 'idle'" class="build-progress">
        <el-steps :active="activeStepIndex" finish-status="success" align-center style="margin-bottom: 20px">
          <el-step
            v-for="(step, idx) in pipelineSteps"
            :key="idx"
            :title="step.title"
            :status="getStepStatus(idx)"
          />
        </el-steps>

        <div class="build-status-bar">
          <el-progress
            :percentage="Math.round(buildStatus.progress * 100)"
            :status="buildStatus.status === 'completed' ? 'success' : buildStatus.status === 'failed' ? 'exception' : undefined"
          />
          <p class="build-message">{{ buildStatus.message }}</p>
        </div>

        <!-- Stage Detail Cards -->
        <div class="stage-detail-area" v-if="hasAnyDetail">
          <div v-if="stageDetails.stage1" class="stage-card">
            <div class="stage-card-header">
              <el-icon><Document /></el-icon>
              <span>模式分析</span>
              <el-tag size="small" type="info">{{ stageDetails.stage1.tables?.length || 0 }} 张表</el-tag>
            </div>
            <el-table :data="stageDetails.stage1.tables || []" size="small" border max-height="240">
              <el-table-column prop="name" label="表名" min-width="180" />
              <el-table-column prop="business_object" label="业务对象" min-width="150" />
              <el-table-column prop="column_count" label="列数" width="80" align="center" />
            </el-table>
          </div>

          <div v-if="stageDetails.stage2" class="stage-card">
            <div class="stage-card-header">
              <el-icon><Box /></el-icon>
              <span>实体抽取</span>
              <el-tag size="small" type="success">{{ stageDetails.stage2.entities?.length || 0 }} 个实体</el-tag>
            </div>
            <div class="entity-tags">
              <el-tag v-for="ent in stageDetails.stage2.entities || []" :key="ent.name" class="entity-tag" effect="plain">
                <span class="ent-label">{{ ent.label || ent.name }}</span>
                <span class="ent-meta">PK: {{ ent.primary_key }} | {{ ent.prop_count }} 属性</span>
              </el-tag>
            </div>
          </div>

          <div v-if="stageDetails.stage3" class="stage-card">
            <div class="stage-card-header">
              <el-icon><Connection /></el-icon>
              <span>关系发现</span>
              <el-tag size="small" type="warning">{{ stageDetails.stage3.relations?.length || 0 }} 个关系</el-tag>
            </div>
            <div class="relation-list">
              <div v-for="rel in stageDetails.stage3.relations || []" :key="rel.name" class="relation-item">
                <span class="rel-source">{{ rel.source }}</span>
                <span class="rel-arrow">
                  <el-icon><Right /></el-icon>
                  <span class="rel-name">{{ rel.label || rel.name }}</span>
                  <el-icon><Right /></el-icon>
                </span>
                <span class="rel-target">{{ rel.target }}</span>
              </div>
            </div>
          </div>

          <div v-if="stageDetails.stage4" class="stage-card">
            <div class="stage-card-header">
              <el-icon><MagicStick /></el-icon>
              <span>本体优化</span>
              <el-tag size="small" type="danger">最终结果</el-tag>
            </div>
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="领域">{{ stageDetails.stage4.domain || '-' }}</el-descriptions-item>
              <el-descriptions-item label="实体数">{{ stageDetails.stage4.entity_count || 0 }}</el-descriptions-item>
              <el-descriptions-item label="关系数">{{ stageDetails.stage4.relation_count || 0 }}</el-descriptions-item>
              <el-descriptions-item label="描述">{{ stageDetails.stage4.description || '-' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
      </div>

      <!-- Ontology Content -->
      <div v-if="ontology && ontology.entities" class="ontology-content">
        <el-descriptions title="本体概览" :column="3" border style="margin-top: 16px">
          <el-descriptions-item label="领域">{{ ontology.domain || '-' }}</el-descriptions-item>
          <el-descriptions-item label="实体数量">{{ ontology.entities?.length || 0 }}</el-descriptions-item>
          <el-descriptions-item label="关系数量">{{ ontology.relations?.length || 0 }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="3">{{ ontology.description || '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-top: 20px">实体定义</h4>
        <el-table :data="ontology.entities" size="small" border style="margin-top: 8px">
          <el-table-column prop="label" label="中文标签" width="150" />
          <el-table-column prop="name" label="实体名" width="180">
            <template #default="{ row }">
              <span style="color: #909399">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" />
          <el-table-column prop="primary_key" label="主键" width="150" />
          <el-table-column label="属性数" width="80">
            <template #default="{ row }">{{ row.properties?.length || 0 }}</template>
          </el-table-column>
        </el-table>

        <h4 style="margin-top: 20px">关系定义</h4>
        <el-table :data="ontology.relations" size="small" border style="margin-top: 8px">
          <el-table-column prop="label" label="中文标签" width="150" />
          <el-table-column prop="name" label="关系名" width="180">
            <template #default="{ row }">
              <span style="color: #909399">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="source_entity" label="源实体" width="150" />
          <el-table-column prop="target_entity" label="目标实体" width="150" />
          <el-table-column prop="cardinality" label="基数" width="80" />
          <el-table-column prop="description" label="描述" />
        </el-table>

        <div style="margin-top: 16px">
          <el-button type="success" @click="handleLoadGraph" :loading="loadingGraph">
            加载到知识图谱
          </el-button>
        </div>

        <div v-if="loadStatus.status && loadStatus.status !== 'no_task'" class="load-status" style="margin-top: 12px">
          <el-alert
            :title="loadStatusTitle"
            :type="loadStatus.status === 'success' ? 'success' : loadStatus.status === 'failed' ? 'error' : 'info'"
            :closable="loadStatus.status === 'success' || loadStatus.status === 'failed'"
            show-icon
          >
            <template #default v-if="loadStatus.status === 'running'">
              <el-progress :percentage="Math.round(loadStatus.progress || 0)" style="margin-top: 4px" />
            </template>
          </el-alert>
        </div>
      </div>

      <el-empty v-else-if="!building" description="暂无本体定义，请先上传数据并构建本体" />
    </el-card>

    <!-- Build Log Dialog -->
    <el-dialog v-model="showBuildLog" title="本体构建记录" width="900px" top="5vh">
      <div v-if="versions.length === 0" style="text-align: center; padding: 20px; color: #909399">暂无构建记录</div>
      <div v-else>
        <el-table :data="versions" size="small" border highlight-current-row @row-click="handleVersionClick" style="margin-bottom: 16px">
          <el-table-column prop="version" label="版本" width="80" align="center">
            <template #default="{ row }">v{{ row.version }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="构建时间" width="200">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '当前版本' : '历史版本' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click.stop="loadVersionDetail(row.id)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- Version Detail / Reasoning Log -->
        <div v-if="versionDetail" class="version-detail">
          <h4 style="margin-bottom: 12px">v{{ versionDetail.version }} 构建推理过程</h4>
          <div v-for="(log, idx) in versionDetail.reasoning_log || []" :key="idx" class="reasoning-stage">
            <div class="reasoning-stage-header">
              <el-tag size="small" :type="stageTagType(log.stage)">{{ stageLabel(log.stage) }}</el-tag>
            </div>
            <div class="reasoning-content">
              <pre class="reasoning-json">{{ formatJson(log.result) }}</pre>
            </div>
          </div>
          <div v-if="!versionDetail.reasoning_log?.length" style="color: #909399; text-align: center; padding: 16px">
            该版本暂无推理记录
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, watch, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Box, Connection, MagicStick, Right } from '@element-plus/icons-vue'
import { buildOntology, getBuildStatus, getOntology, getOntologyVersions, getOntologyVersionDetail, loadGraphData, getLoadStatus } from '@/api/graph'

const projectId = inject<any>('currentProjectId')
const ontology = ref<any>(null)
const building = ref(false)
const loadingGraph = ref(false)
const buildStatus = ref<any>({ status: 'idle', progress: 0, current_stage: '', message: '', stage_summaries: {}, stage_details: {} })
const loadStatus = ref<any>({ status: 'no_task', progress: 0 })
const showBuildLog = ref(false)
const versions = ref<any[]>([])
const versionDetail = ref<any>(null)
let pollTimer: any = null
let loadPollTimer: any = null

const pipelineSteps = [
  { title: '模式分析', key: 'stage1' },
  { title: '实体抽取', key: 'stage2' },
  { title: '关系发现', key: 'stage3' },
  { title: '本体优化', key: 'stage4' },
]

const stageIndexMap: Record<string, number> = {
  stage1: 0, stage2: 1, stage3: 2, stage4: 3, completed: 4,
}

const activeStepIndex = computed(() => stageIndexMap[buildStatus.value.status] ?? -1)
const stageDetails = computed(() => buildStatus.value.stage_details || {})
const hasAnyDetail = computed(() => {
  const d = stageDetails.value
  return d.stage1 || d.stage2 || d.stage3 || d.stage4
})

function getStepStatus(idx: number) {
  const active = activeStepIndex.value
  if (buildStatus.value.status === 'failed' && idx === active) return 'error'
  if (idx < active) return 'finish'
  if (idx === active) return 'process'
  return 'wait'
}

const loadStatusTitle = computed(() => {
  const s = loadStatus.value
  if (s.status === 'running') return '正在加载数据到知识图谱（将清空旧图谱后重新导入）...'
  if (s.status === 'success') return `加载完成：${s.total_nodes || 0} 个节点，${s.total_relations || 0} 个关系`
  if (s.status === 'failed') return `加载失败：${s.error_message || '未知错误'}`
  return ''
})

function stageLabel(stage: string) {
  const map: Record<string, string> = { schema_analysis: '模式分析', entity_extraction: '实体抽取', relation_discovery: '关系发现', ontology_refinement: '本体优化' }
  return map[stage] || stage
}

function stageTagType(stage: string) {
  const map: Record<string, string> = { schema_analysis: 'info', entity_extraction: 'success', relation_discovery: 'warning', ontology_refinement: 'danger' }
  return map[stage] || 'info'
}

function formatTime(iso: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

function formatJson(obj: any) {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

async function loadOntology() {
  if (!projectId?.value) return
  try {
    const res = await getOntology(projectId.value)
    ontology.value = res.data
  } catch (e) { /* ignore */ }
}

async function loadVersions() {
  if (!projectId?.value) return
  try {
    const res = await getOntologyVersions(projectId.value)
    versions.value = res.data || []
  } catch (e) { /* ignore */ }
}

async function loadVersionDetail(versionId: string) {
  if (!projectId?.value) return
  try {
    const res = await getOntologyVersionDetail(projectId.value, versionId)
    versionDetail.value = res.data
  } catch (e: any) {
    ElMessage.error('加载版本详情失败')
  }
}

function handleVersionClick(row: any) {
  loadVersionDetail(row.id)
}

async function handleBuild() {
  if (!projectId?.value) return
  building.value = true
  buildStatus.value = { status: 'stage1', progress: 0, current_stage: '模式分析', message: '正在分析数据表结构...', stage_summaries: {}, stage_details: {} }
  try {
    await buildOntology(projectId.value)
    ElMessage.info('本体构建已启动')
    startPolling()
  } catch (e: any) {
    ElMessage.error(e.message || '构建启动失败')
    building.value = false
    buildStatus.value = { status: 'idle', progress: 0, current_stage: '', message: '', stage_summaries: {}, stage_details: {} }
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await getBuildStatus(projectId.value)
      buildStatus.value = res.data || {}
      if (res.data?.status === 'completed') {
        building.value = false
        stopPolling()
        ElMessage.success('本体构建完成')
        loadOntology()
        loadVersions()
      } else if (res.data?.status === 'failed') {
        building.value = false
        stopPolling()
        ElMessage.error('本体构建失败: ' + res.data.message)
      }
    } catch (e) { /* ignore */ }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

async function handleLoadGraph() {
  if (!projectId?.value) return
  loadingGraph.value = true
  loadStatus.value = { status: 'running', progress: 0 }
  try {
    await loadGraphData(projectId.value)
    ElMessage.info('数据加载已启动（旧图谱将被清空后重新导入）')
    startLoadPolling()
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
    loadingGraph.value = false
    loadStatus.value = { status: 'no_task' }
  }
}

function startLoadPolling() {
  stopLoadPolling()
  loadPollTimer = setInterval(async () => {
    try {
      const res = await getLoadStatus(projectId.value)
      loadStatus.value = res.data || {}
      if (res.data?.status === 'success') {
        loadingGraph.value = false
        stopLoadPolling()
        ElMessage.success(`加载完成：${res.data.total_nodes || 0} 节点，${res.data.total_relations || 0} 关系`)
      } else if (res.data?.status === 'failed') {
        loadingGraph.value = false
        stopLoadPolling()
        ElMessage.error('加载失败: ' + (res.data.error_message || ''))
      }
    } catch (e) { /* ignore */ }
  }, 2000)
}

function stopLoadPolling() {
  if (loadPollTimer) { clearInterval(loadPollTimer); loadPollTimer = null }
}

watch(() => projectId?.value, () => {
  loadOntology()
  loadVersions()
  loadStatus.value = { status: 'no_task' }
  versionDetail.value = null
})

watch(showBuildLog, (val) => {
  if (val) { loadVersions(); versionDetail.value = null }
})

onMounted(() => {
  loadOntology()
  loadVersions()
})

onUnmounted(() => {
  stopPolling()
  stopLoadPolling()
})
</script>

<style scoped>
.ontology-list-page { max-width: 1200px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.build-progress { margin-bottom: 16px; padding: 16px; background: #f9fafb; border-radius: 8px; }
.build-status-bar { margin-top: 12px; }
.build-message { margin-top: 4px; font-size: 13px; color: #606266; }

.stage-detail-area { margin-top: 20px; display: flex; flex-direction: column; gap: 16px; }
.stage-card { background: #fff; border: 1px solid #e4e7ed; border-radius: 8px; padding: 16px; }
.stage-card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 15px; font-weight: 600; color: #303133; }
.stage-card-header .el-icon { font-size: 18px; color: #409eff; }

.entity-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.entity-tag { padding: 8px 12px; height: auto; line-height: 1.4; }
.ent-label { font-weight: 600; margin-right: 6px; }
.ent-meta { font-size: 12px; color: #909399; }

.relation-list { display: flex; flex-direction: column; gap: 8px; }
.relation-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #f5f7fa; border-radius: 6px; font-size: 14px; }
.rel-source, .rel-target { font-weight: 600; color: #303133; padding: 2px 8px; background: #ecf5ff; border-radius: 4px; }
.rel-arrow { display: flex; align-items: center; gap: 4px; color: #909399; }
.rel-name { color: #e6a23c; font-weight: 500; font-size: 13px; }

/* Build Log Dialog */
.version-detail { border-top: 1px solid #e4e7ed; padding-top: 16px; }
.reasoning-stage { margin-bottom: 16px; border: 1px solid #ebeef5; border-radius: 6px; overflow: hidden; }
.reasoning-stage-header { padding: 8px 12px; background: #f5f7fa; border-bottom: 1px solid #ebeef5; }
.reasoning-content { padding: 12px; }
.reasoning-json { margin: 0; font-size: 12px; line-height: 1.6; color: #606266; white-space: pre-wrap; word-break: break-all; max-height: 400px; overflow-y: auto; background: #fafafa; padding: 8px; border-radius: 4px; }
</style>
