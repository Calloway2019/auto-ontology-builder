<template>
  <div class="graph-page">
    <el-card shadow="never" class="graph-card">
      <template #header>
        <div class="card-header">
          <span>知识图谱可视化</span>
          <div class="toolbar">
            <el-button size="small" @click="refreshGraph">刷新</el-button>
            <el-select v-model="nodeLimit" size="small" style="width: 120px" @change="refreshGraph">
              <el-option :value="30" label="30 节点" />
              <el-option :value="50" label="50 节点" />
              <el-option :value="100" label="100 节点" />
              <el-option :value="300" label="300 节点" />
            </el-select>
          </div>
        </div>
      </template>

      <!-- Stats Bar -->
      <div v-if="stats" class="stats-bar">
        <el-tag type="info">节点: {{ stats.total_nodes }}</el-tag>
        <el-tag type="info">关系: {{ stats.total_edges }}</el-tag>
        <el-tag
          v-for="(info, type) in stats.node_types"
          :key="type"
          :color="getNodeColor(String(type))"
          style="color: #fff; margin-left: 4px"
        >
          {{ info.label || type }}: {{ info.count }}
        </el-tag>
      </div>

      <!-- Graph Container -->
      <div ref="graphContainer" class="graph-container" v-loading="loading" />

      <!-- Node Detail Panel -->
      <el-drawer
        v-model="showNodeDetail"
        :title="selectedNode?.type_label || selectedNode?.type || '节点详情'"
        :size="360"
        :with-header="true"
      >
        <div v-if="selectedNode">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="类型">
              <el-tag size="small">{{ selectedNode.type_label || selectedNode.type }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="标签">{{ selectedNode.label }}</el-descriptions-item>
            <el-descriptions-item
              v-for="(val, key) in selectedNode.properties"
              :key="key"
              :label="String(key)"
            >
              {{ val ?? '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </el-drawer>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { getGraphVisualization, getGraphStats } from '@/api/graph'

const projectId = inject<any>('currentProjectId')
const graphContainer = ref<HTMLElement | null>(null)
const loading = ref(false)
const stats = ref<any>(null)
const nodeLimit = ref(100)
const showNodeDetail = ref(false)
const selectedNode = ref<any>(null)
let graphInstance: any = null

// Color palette for different node types
const colors = [
  '#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399',
  '#00C9A7', '#845EC2', '#FF6F91', '#FFC75F', '#4B4453',
]
const typeColorMap: Record<string, string> = {}
let colorIndex = 0

function getNodeColor(type: string): string {
  if (!typeColorMap[type]) {
    typeColorMap[type] = colors[colorIndex % colors.length]
    colorIndex++
  }
  return typeColorMap[type]
}

async function loadStats() {
  if (!projectId?.value) return
  try {
    const res = await getGraphStats(projectId.value)
    stats.value = res.data
  } catch (e) {
    // ignore
  }
}

async function refreshGraph() {
  if (!projectId?.value || !graphContainer.value) return
  loading.value = true

  try {
    const res = await getGraphVisualization(projectId.value, nodeLimit.value)
    const data = res.data || { nodes: [], edges: [] }
    await loadStats()
    await renderGraph(data)
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}

async function renderGraph(data: { nodes: any[]; edges: any[] }) {
  // Clean up previous instance
  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }

  if (!graphContainer.value || data.nodes.length === 0) return

  try {
    const G6 = await import('@antv/g6')

    // Transform data for G6
    const nodes = data.nodes.map((n: any) => ({
      id: n.id,
      data: {
        label: n.label || n.id,
        type: n.type,
        type_label: n.type_label || n.type,
        properties: n.properties,
        nodeColor: getNodeColor(n.type),
      },
    }))

    const edges = data.edges.map((e: any) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      data: {
        label: e.type_label || e.label || e.type,
      },
    }))

    const container = graphContainer.value
    const width = container.offsetWidth
    const height = container.offsetHeight || 600

    graphInstance = new G6.Graph({
      container,
      width,
      height,
      data: { nodes, edges },
      layout: {
        type: 'force',
        preventOverlap: true,
        nodeSize: 40,
      },
      node: {
        style: {
          size: 36,
          fill: (d: any) => d.data?.nodeColor || '#409EFF',
          stroke: '#fff',
          lineWidth: 2,
          labelText: (d: any) => {
            const label = d.data?.label || ''
            return label.length > 8 ? label.substring(0, 8) + '...' : label
          },
          labelFill: '#333',
          labelFontSize: 11,
          labelPlacement: 'bottom',
        },
      },
      edge: {
        style: {
          stroke: '#C0C4CC',
          lineWidth: 1,
          endArrow: true,
          labelText: (d: any) => d.data?.label || '',
          labelFontSize: 9,
          labelFill: '#909399',
        },
      },
      behaviors: ['drag-canvas', 'zoom-canvas', 'drag-element', 'click-select'],
    })

    graphInstance.render()

    // Click node event
    graphInstance.on('node:click', (evt: any) => {
      const nodeData = nodes.find((n: any) => n.id === evt.target.id)
      if (nodeData) {
        selectedNode.value = {
          id: nodeData.id,
          label: nodeData.data.label,
          type: nodeData.data.type,
          type_label: nodeData.data.type_label,
          properties: nodeData.data.properties || {},
        }
        showNodeDetail.value = true
      }
    })
  } catch (e) {
    console.warn('G6 render failed:', e)
  }
}

watch(() => projectId?.value, () => {
  refreshGraph()
})

onMounted(() => {
  nextTick(() => refreshGraph())
})

onUnmounted(() => {
  if (graphInstance) {
    graphInstance.destroy()
    graphInstance = null
  }
})
</script>

<style scoped>
.graph-page {
  height: calc(100vh - 140px);
}
.graph-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.graph-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}
.stats-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.graph-container {
  flex: 1;
  min-height: 500px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: #fafafa;
}
</style>
