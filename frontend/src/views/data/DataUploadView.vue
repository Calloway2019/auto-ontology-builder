<template>
  <div class="data-upload-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>数据上传</span>
        </div>
      </template>

      <el-alert
        v-if="!projectId"
        title="请先创建或选择一个项目"
        description="点击页面顶部项目选择器右侧的 + 按钮新建项目"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <!-- File Upload -->
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="fileList"
        accept=".xlsx,.xls,.csv"
        drag
        multiple
      >
        <el-icon class="el-icon--upload" :size="40"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">支持 .xlsx, .xls, .csv 格式</div>
        </template>
      </el-upload>

      <el-button
        type="primary"
        :loading="uploading"
        :disabled="fileList.length === 0 || !projectId"
        style="margin-top: 16px"
        @click="handleUpload"
      >
        上传并解析
      </el-button>
    </el-card>

    <!-- Upload Results -->
    <el-card v-if="uploadResults.length > 0" shadow="never" style="margin-top: 16px">
      <template #header>
        <span>解析结果</span>
      </template>

      <el-collapse>
        <el-collapse-item
          v-for="(result, idx) in uploadResults"
          :key="idx"
          :title="`${result.name} (${result.row_count} 行, ${result.columns?.length || 0} 列)`"
        >
          <el-table :data="result.columns" size="small" border max-height="300">
            <el-table-column prop="name" label="列名" width="200" />
            <el-table-column prop="dtype" label="类型" width="100" />
            <el-table-column prop="unique_count" label="唯一值数" width="100" />
            <el-table-column prop="null_rate" label="空值率" width="100">
              <template #default="{ row }">
                {{ (row.null_rate * 100).toFixed(1) }}%
              </template>
            </el-table-column>
            <el-table-column prop="sample_values" label="样本值">
              <template #default="{ row }">
                {{ row.sample_values?.join(', ') }}
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- Datasource List -->
    <el-card v-if="datasources.length > 0" shadow="never" style="margin-top: 16px">
      <template #header>
        <span>已有数据源</span>
      </template>

      <el-table :data="datasources" size="small" border>
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="source_type" label="类型" width="100" />
        <el-table-column prop="row_count" label="行数" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'analyzed' ? 'success' : 'info'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button type="danger" size="small" link @click="handleDeleteDs(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadFiles, listDatasources, deleteDatasource } from '@/api/ontology'
import type { UploadUserFile } from 'element-plus'

const projectId = inject<any>('currentProjectId')
const fileList = ref<UploadUserFile[]>([])
const uploading = ref(false)
const uploadResults = ref<any[]>([])
const datasources = ref<any[]>([])

function handleFileChange(_file: any, list: UploadUserFile[]) {
  fileList.value = list
}

async function handleUpload() {
  if (!projectId?.value) {
    ElMessage.warning('请先选择或创建一个项目')
    return
  }
  uploading.value = true
  try {
    const files = fileList.value.map((f) => f.raw as File).filter(Boolean)
    const res = await uploadFiles(projectId.value, files)
    uploadResults.value = res.data || []
    ElMessage.success('上传解析成功')
    fileList.value = []
    loadDatasources()
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function loadDatasources() {
  if (!projectId?.value) return
  try {
    const res = await listDatasources(projectId.value)
    datasources.value = res.data || []
  } catch (e) {
    // ignore
  }
}

async function handleDeleteDs(dsId: string) {
  if (!projectId?.value) return
  await deleteDatasource(projectId.value, dsId)
  loadDatasources()
}

watch(() => projectId?.value, () => {
  loadDatasources()
})

onMounted(() => {
  loadDatasources()
})
</script>

<style scoped>
.data-upload-page {
  max-width: 1000px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
