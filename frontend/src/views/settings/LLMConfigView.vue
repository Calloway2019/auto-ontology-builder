<template>
  <div class="llm-config-page">
    <el-card shadow="never" style="max-width: 600px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>LLM 模型配置</span>
          <el-tag v-if="configStatus === 'configured'" type="success" size="small">已配置</el-tag>
          <el-tag v-else-if="configStatus === 'not_configured'" type="danger" size="small">未配置</el-tag>
          <el-tag v-else type="info" size="small">检测中...</el-tag>
        </div>
      </template>

      <el-form :model="config" label-width="120px">
        <el-form-item label="API Base URL">
          <el-input v-model="config.base_url" placeholder="https://api.deepseek.com/v1" />
          <div class="input-tip">Docker 部署时，如使用本地模型请用 http://host.docker.internal:端口/v1 替代 localhost</div>
        </el-form-item>

        <el-form-item label="API Key">
          <el-input
            v-model="config.api_key"
            :type="showKey ? 'text' : 'password'"
            placeholder="sk-..."
          >
            <template #append>
              <el-button @click="showKey = !showKey">
                <el-icon><View v-if="!showKey" /><Hide v-else /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="模型名称">
          <el-input v-model="config.model_name" placeholder="deepseek-chat" />
          <div class="input-tip">常见模型: deepseek-chat, qwen-72b, gpt-4o, chatglm4</div>
        </el-form-item>

        <el-form-item style="margin-top: 20px">
          <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
          <el-button @click="handleTest" :loading="testing">测试连接</el-button>
        </el-form-item>

        <!-- Connection Status -->
        <el-form-item v-if="testResult" label="连接状态">
          <el-tag :type="testResult.status === 'connected' ? 'success' : 'danger'">
            {{ testResult.status === 'connected' ? '连接成功' : '连接失败' }}
          </el-tag>
          <span v-if="testResult.error" style="color: #F56C6C; margin-left: 8px; font-size: 13px">
            {{ testResult.error }}
          </span>
          <span v-if="testResult.response" style="color: #67C23A; margin-left: 8px; font-size: 13px">
            {{ testResult.response }}
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- System Health -->
    <el-card shadow="never" style="max-width: 600px; margin-top: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>系统状态</span>
          <el-button size="small" @click="loadHealth">刷新</el-button>
        </div>
      </template>

      <el-descriptions :column="1" border size="small" v-if="health">
        <el-descriptions-item label="整体状态">
          <el-tag :type="health.status === 'healthy' ? 'success' : 'warning'">
            {{ health.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Neo4j">
          <el-tag :type="health.neo4j?.status === 'connected' ? 'success' : 'danger'" size="small">
            {{ health.neo4j?.status || 'unknown' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="LLM">
          <el-tag :type="health.llm?.status === 'connected' ? 'success' : 'danger'" size="small">
            {{ health.llm?.status || 'unknown' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSystemConfig, updateLLMConfig, testLLMConnection, healthCheck } from '@/api/llm'

const config = ref({
  api_key: '',
  base_url: 'https://api.deepseek.com/v1',
  model_name: 'deepseek-chat',
  temperature: 0.1,
  max_tokens: 4096,
})

const showKey = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref<any>(null)
const health = ref<any>(null)
const configStatus = ref<'loading' | 'configured' | 'not_configured'>('loading')

async function loadConfig() {
  try {
    const res = await getSystemConfig()
    const llm = res.data?.llm
    if (llm) {
      config.value.base_url = llm.base_url || config.value.base_url
      config.value.model_name = llm.model_name || config.value.model_name
      configStatus.value = llm.is_configured ? 'configured' : 'not_configured'
      // Don't overwrite API key if masked
      if (llm.api_key && !llm.api_key.includes('****')) {
        config.value.api_key = llm.api_key
      }
    } else {
      configStatus.value = 'not_configured'
    }
  } catch (e) {
    configStatus.value = 'not_configured'
  }
}

async function handleSave() {
  saving.value = true
  try {
    await updateLLMConfig(config.value)
    ElMessage.success('配置已保存')
    configStatus.value = 'configured'
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  testing.value = true
  testResult.value = null
  try {
    // Save first, then test
    await updateLLMConfig(config.value)
    const res = await testLLMConnection()
    testResult.value = res.data
    if (res.data?.status === 'connected') {
      ElMessage.success('连接成功')
    } else {
      ElMessage.error('连接失败: ' + (res.data?.error || ''))
    }
  } catch (e: any) {
    testResult.value = { status: 'error', error: e.message }
    ElMessage.error('测试失败')
  } finally {
    testing.value = false
  }
}

async function loadHealth() {
  try {
    const res = await healthCheck()
    health.value = res.data
  } catch (e) {
    // ignore
  }
}

onMounted(() => {
  loadConfig()
  loadHealth()
})
</script>

<style scoped>
.llm-config-page {
  max-width: 800px;
}
.input-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
