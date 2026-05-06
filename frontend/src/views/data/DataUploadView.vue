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

      <!-- Upload area + description input side by side -->
      <div class="upload-row">
        <!-- Data source file -->
        <div class="upload-col">
          <div class="upload-label">数据源文件</div>
          <el-upload
            ref="dataUploadRef"
            :auto-upload="false"
            :on-change="handleDataFileChange"
            :file-list="dataFileList"
            accept=".xlsx,.xls,.csv"
            drag
            :limit="1"
            :on-exceed="() => ElMessage.warning('请先移除已选文件')"
          >
            <el-icon class="el-icon--upload" :size="32"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽或 <em>点击上传</em> 数据表
            </div>
            <template #tip>
              <div class="el-upload__tip">支持 .xlsx / .xls / .csv</div>
            </template>
          </el-upload>
        </div>

        <!-- Field description text input -->
        <div class="upload-col">
          <div class="upload-label">字段描述信息（可选）</div>
          <el-input
            v-model="descText"
            type="textarea"
            :rows="7"
            placeholder="请输入或粘贴字段的描述信息，例如：&#10;订单编号：唯一标识每笔订单的编号&#10;客户名称：下单客户的全称&#10;产品型号：所订购产品的型号规格&#10;&#10;支持任意格式，大模型会自动匹配到对应列"
            resize="vertical"
          />
          <div class="desc-tip">
            输入字段含义描述后，大模型将自动匹配到数据表各列
          </div>
        </div>
      </div>

      <div style="margin-top: 16px">
        <el-button
          type="primary"
          :loading="uploading"
          :disabled="dataFileList.length === 0 || !projectId"
          @click="handleUpload"
        >
          {{ descText.trim() ? '上传并智能匹配描述' : '上传并解析' }}
        </el-button>
      </div>
    </el-card>

    <!-- Upload Result: Column Metadata with auto-filled descriptions -->
    <el-card v-if="uploadResult" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>解析结果：{{ uploadResult.name }} ({{ uploadResult.row_count }} 行, {{ uploadResult.columns?.length || 0 }} 列)</span>
          <el-tag v-if="descMatched" type="success" size="small">描述已自动匹配</el-tag>
        </div>
      </template>

      <el-table :data="uploadResult.columns" size="small" border>
        <el-table-column prop="name" label="列名" width="160" />
        <el-table-column prop="dtype" label="类型" width="100" />
        <el-table-column prop="unique_count" label="唯一值数" width="90" align="center" />
        <el-table-column prop="null_rate" label="空值率" width="80" align="center">
          <template #default="{ row }">
            {{ (row.null_rate * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column prop="sample_values" label="样本值" min-width="160">
          <template #default="{ row }">
            {{ row.sample_values?.join(', ') }}
          </template>
        </el-table-column>
        <el-table-column label="含义描述" min-width="220">
          <template #default="{ row }">
            <el-input
              v-model="row.description"
              size="small"
              placeholder="请输入该列的业务含义"
              clearable
            />
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 12px; text-align: right">
        <el-button type="success" :loading="savingDesc" @click="handleSaveDescriptions">
          保存列描述
        </el-button>
      </div>
    </el-card>

    <!-- Datasource List -->
    <el-card v-if="datasources.length > 0" shadow="never" style="margin-top: 16px">
      <template #header>
        <span>已有数据源</span>
      </template>

      <el-table :data="datasources" size="small" border row-key="id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 8px 16px">
              <el-table :data="row.columns_meta || []" size="small" border>
                <el-table-column prop="name" label="列名" width="160" />
                <el-table-column prop="dtype" label="类型" width="100" />
                <el-table-column prop="unique_count" label="唯一值数" width="90" align="center" />
                <el-table-column prop="null_rate" label="空值率" width="80" align="center">
                  <template #default="{ row: col }">
                    {{ col.null_rate != null ? (col.null_rate * 100).toFixed(1) + '%' : '-' }}
                  </template>
                </el-table-column>
                <el-table-column prop="sample_values" label="样本值" min-width="140">
                  <template #default="{ row: col }">
                    {{ col.sample_values?.join(', ') || '-' }}
                  </template>
                </el-table-column>
                <el-table-column prop="description" label="含义描述" min-width="200">
                  <template #default="{ row: col }">
                    <span v-if="editingDsId !== row.id">{{ col.description || '-' }}</span>
                    <el-input
                      v-else
                      v-model="col.description"
                      size="small"
                      placeholder="请输入含义"
                      clearable
                    />
                  </template>
                </el-table-column>
              </el-table>
              <div style="margin-top: 8px; text-align: right">
                <el-button
                  v-if="editingDsId !== row.id"
                  type="primary" size="small" link
                  @click="editingDsId = row.id"
                >
                  编辑描述
                </el-button>
                <template v-else>
                  <el-button size="small" @click="editingDsId = ''">取消</el-button>
                  <el-button type="success" size="small" :loading="savingDesc" @click="handleSaveExistingDesc(row)">
                    保存
                  </el-button>
                </template>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="source_type" label="类型" width="100" />
        <el-table-column prop="row_count" label="行数" width="100" />
        <el-table-column label="列描述" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              :type="hasDescriptions(row) ? 'success' : 'info'"
              size="small"
            >
              {{ hasDescriptions(row) ? '已填写' : '未填写' }}
            </el-tag>
          </template>
        </el-table-column>
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
import { uploadFiles, listDatasources, deleteDatasource, updateColumnDescriptions, uploadWithDesc } from '@/api/ontology'
import type { UploadUserFile } from 'element-plus'

const projectId = inject<any>('currentProjectId')
const dataFileList = ref<UploadUserFile[]>([])
const descText = ref('')
const uploading = ref(false)
const uploadResult = ref<any>(null)
const descMatched = ref(false)
const datasources = ref<any[]>([])
const savingDesc = ref(false)
const editingDsId = ref('')

function handleDataFileChange(_file: any, list: UploadUserFile[]) {
  dataFileList.value = list.slice(-1)
}

function hasDescriptions(row: any): boolean {
  const cols = row.columns_meta || []
  return cols.some((c: any) => c.description && c.description.trim())
}

async function handleUpload() {
  if (!projectId?.value) {
    ElMessage.warning('请先选择或创建一个项目')
    return
  }
  uploading.value = true
  descMatched.value = false

  try {
    const dataFile = dataFileList.value[0]?.raw as File
    if (!dataFile) return

    let res: any
    const hasDesc = descText.value.trim().length > 0
    if (hasDesc) {
      res = await uploadWithDesc(projectId.value, dataFile, descText.value)
      descMatched.value = true
    } else {
      res = await uploadFiles(projectId.value, [dataFile])
    }

    const result = hasDesc ? res.data : (res.data || [])[0]
    if (!result) {
      ElMessage.error('上传失败：无返回结果')
      return
    }
    if (result.error) {
      ElMessage.error('上传失败: ' + result.error)
      return
    }
    if (result.columns) {
      result.columns.forEach((col: any) => {
        if (!col.description) col.description = ''
      })
    }
    uploadResult.value = result
    ElMessage.success(descMatched.value ? '上传成功，字段描述已由大模型自动匹配' : '上传解析成功，请填写列含义描述')
    dataFileList.value = []
    descText.value = ''
    loadDatasources()
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleSaveDescriptions() {
  if (!projectId?.value || !uploadResult.value?.id) return
  savingDesc.value = true
  try {
    const columns = (uploadResult.value.columns || []).map((c: any) => ({
      name: c.name,
      description: c.description || '',
    }))
    await updateColumnDescriptions(projectId.value, uploadResult.value.id, columns)
    ElMessage.success('列描述已保存')
    uploadResult.value = null
    loadDatasources()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingDesc.value = false
  }
}

async function handleSaveExistingDesc(row: any) {
  if (!projectId?.value) return
  savingDesc.value = true
  try {
    const columns = (row.columns_meta || []).map((c: any) => ({
      name: c.name,
      description: c.description || '',
    }))
    await updateColumnDescriptions(projectId.value, row.id, columns)
    ElMessage.success('列描述已保存')
    editingDsId.value = ''
    loadDatasources()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingDesc.value = false
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
  uploadResult.value = null
  editingDsId.value = ''
  descMatched.value = false
  descText.value = ''
  loadDatasources()
})

onMounted(() => {
  loadDatasources()
})
</script>

<style scoped>
.data-upload-page {
  max-width: 1200px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.upload-row {
  display: flex;
  gap: 20px;
}
.upload-col {
  flex: 1;
  min-width: 0;
}
.upload-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}
.desc-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}
</style>
