<template>
  <div class="chat-page">
    <el-card shadow="never" class="chat-card">
      <template #header>
        <div class="chat-header">
          <span>智能问答</span>
          <div class="chat-header-actions">
            <el-button size="small" @click="handleNewChat">
              <el-icon><Plus /></el-icon> 新建对话
            </el-button>
            <el-button size="small" @click="showHistory = true">
              <el-icon><Clock /></el-icon> 历史记录
            </el-button>
          </div>
        </div>
      </template>

      <!-- Message List -->
      <div ref="messageListRef" class="message-list">
        <div v-if="messages.length === 0" class="welcome-message">
          <el-icon :size="48" color="#409EFF"><ChatDotRound /></el-icon>
          <h3>欢迎使用本体智能问答</h3>
          <p>您可以基于已构建的知识图谱进行自然语言提问</p>
          <div class="suggested-questions">
            <el-button
              v-for="q in suggestedQuestions"
              :key="q"
              size="small"
              @click="handleSuggestedQuestion(q)"
            >
              {{ q }}
            </el-button>
          </div>
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="message-item"
          :class="msg.role"
        >
          <div class="message-avatar">
            <el-avatar :size="32" :style="{ background: msg.role === 'user' ? '#409EFF' : '#67C23A' }">
              {{ msg.role === 'user' ? 'U' : 'AI' }}
            </el-avatar>
          </div>
          <div class="message-bubble">
            <!-- Thinking Process (collapsible) -->
            <div v-if="msg.role === 'assistant' && msg.meta && (msg.meta.intent || msg.meta.cypher)" class="thinking-process">
              <el-collapse>
                <el-collapse-item>
                  <template #title>
                    <span class="thinking-title">
                      <el-icon><View /></el-icon> 思考过程
                    </span>
                  </template>
                  <div class="thinking-detail">
                    <div v-if="msg.meta.intent" class="thinking-step">
                      <span class="step-label">意图识别：</span>
                      <el-tag size="small" type="info">{{ msg.meta.intent }}</el-tag>
                    </div>
                    <div v-if="msg.meta.cypher" class="thinking-step">
                      <span class="step-label">Cypher 查询：</span>
                      <pre class="cypher-code">{{ msg.meta.cypher }}</pre>
                    </div>
                    <div v-if="msg.meta.raw_result" class="thinking-step">
                      <span class="step-label">查询结果：</span>
                      <pre class="result-code">{{ formatResult(msg.meta.raw_result) }}</pre>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
            <!-- Answer -->
            <div v-if="msg.role === 'assistant'" v-html="renderMd(msg.content)" class="md-content" />
            <div v-else>{{ msg.content }}</div>
            <div v-if="msg.meta" class="message-meta">
              <span v-if="msg.meta.latency_ms" class="latency">{{ msg.meta.latency_ms }}ms</span>
            </div>
          </div>
        </div>

        <div v-if="thinking" class="message-item assistant">
          <div class="message-avatar">
            <el-avatar :size="32" style="background: #67C23A">AI</el-avatar>
          </div>
          <div class="message-bubble thinking">
            <span class="dot-animation">思考中</span>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="chat-input-area">
        <el-input
          v-model="inputText"
          placeholder="请输入您的问题..."
          @keyup.enter="handleSend"
          :disabled="thinking || !projectId"
          size="large"
        >
          <template #append>
            <el-button type="primary" @click="handleSend" :loading="thinking" :disabled="!inputText.trim()">
              发送
            </el-button>
          </template>
        </el-input>
      </div>
    </el-card>

    <!-- History Dialog -->
    <el-dialog v-model="showHistory" title="历史问答记录" width="800px" top="5vh">
      <el-table :data="historyList" size="small" border max-height="500" @row-click="handleHistoryClick" highlight-current-row>
        <el-table-column prop="question" label="问题" min-width="250" show-overflow-tooltip />
        <el-table-column prop="intent" label="意图" width="120" />
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="80" align="center">
          <template #default="{ row }">{{ row.latency_ms }}ms</template>
        </el-table-column>
      </el-table>

      <!-- Selected History Detail -->
      <div v-if="selectedHistory" class="history-detail">
        <h4>问题：{{ selectedHistory.question }}</h4>
        <div v-if="selectedHistory.generated_cypher" class="thinking-step" style="margin-top: 8px">
          <span class="step-label">Cypher：</span>
          <pre class="cypher-code">{{ selectedHistory.generated_cypher }}</pre>
        </div>
        <div style="margin-top: 8px">
          <span class="step-label">回答：</span>
          <div v-html="renderMd(selectedHistory.answer || '无回答')" class="md-content" style="margin-top: 4px" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, inject, nextTick, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Clock, View } from '@element-plus/icons-vue'
import { askQuestion, getQAHistory } from '@/api/chat'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt()

const projectId = inject<any>('currentProjectId')
const inputText = ref('')
const thinking = ref(false)
const messageListRef = ref<HTMLElement | null>(null)
const showHistory = ref(false)
const historyList = ref<any[]>([])
const selectedHistory = ref<any>(null)

interface Message {
  role: 'user' | 'assistant'
  content: string
  meta?: {
    intent?: string
    latency_ms?: number
    cypher?: string
    raw_result?: any
  }
}

const messages = ref<Message[]>([])

const suggestedQuestions = ref([
  '系统中有哪些实体类型？',
  '列出所有实体之间的关系',
  '哪些数据存在异常？',
])

async function loadHistory() {
  if (!projectId?.value) return
  try {
    const res = await getQAHistory(projectId.value, 1, 50)
    const items = res.data || []
    if (items.length > 0) {
      const historyMessages: Message[] = []
      for (const item of [...items].reverse()) {
        historyMessages.push({ role: 'user', content: item.question })
        let rawResult = null
        try {
          rawResult = item.graph_result ? JSON.parse(item.graph_result) : null
        } catch { /* ignore */ }
        historyMessages.push({
          role: 'assistant',
          content: item.answer || '未能生成回答',
          meta: {
            intent: item.intent,
            latency_ms: item.latency_ms,
            cypher: item.generated_cypher,
            raw_result: rawResult,
          },
        })
      }
      messages.value = historyMessages
      scrollToBottom()
    }
  } catch (e) { /* ignore */ }
}

async function loadHistoryList() {
  if (!projectId?.value) return
  try {
    const res = await getQAHistory(projectId.value, 1, 100)
    historyList.value = res.data || []
    selectedHistory.value = null
  } catch (e) { /* ignore */ }
}

function handleHistoryClick(row: any) {
  selectedHistory.value = row
}

function handleNewChat() {
  messages.value = []
  inputText.value = ''
}

function renderMd(text: string) {
  return md.render(text)
}

function formatTime(iso: string) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

function formatResult(obj: any) {
  try {
    const str = JSON.stringify(obj, null, 2)
    return str.length > 1000 ? str.substring(0, 1000) + '\n...(结果已截断)' : str
  } catch {
    return String(obj)
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

function handleSuggestedQuestion(q: string) {
  inputText.value = q
  handleSend()
}

async function handleSend() {
  const question = inputText.value.trim()
  if (!question || !projectId?.value) return

  messages.value.push({ role: 'user', content: question })
  inputText.value = ''
  thinking.value = true
  scrollToBottom()

  try {
    const res = await askQuestion(projectId.value, question)
    const data = res.data
    let rawResult = null
    try {
      rawResult = typeof data.raw_result === 'string' ? JSON.parse(data.raw_result) : data.raw_result
    } catch { rawResult = data.raw_result }
    messages.value.push({
      role: 'assistant',
      content: data.answer || '未能生成回答',
      meta: {
        intent: data.intent,
        latency_ms: data.latency_ms,
        cypher: data.generated_cypher,
        raw_result: rawResult,
      },
    })
  } catch (e: any) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，处理您的问题时出现错误: ' + (e.message || '未知错误'),
    })
  } finally {
    thinking.value = false
    scrollToBottom()
  }
}

watch(() => projectId?.value, () => {
  messages.value = []
  loadHistory()
})

watch(showHistory, (val) => {
  if (val) loadHistoryList()
})

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.chat-page { height: calc(100vh - 140px); max-width: 900px; }
.chat-card { height: 100%; display: flex; flex-direction: column; }
.chat-card :deep(.el-card__body) { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding-bottom: 0; }
.chat-header { display: flex; justify-content: space-between; align-items: center; }
.chat-header-actions { display: flex; gap: 8px; }
.message-list { flex: 1; overflow-y: auto; padding: 16px 0; }
.welcome-message { text-align: center; padding: 60px 0; color: #606266; }
.welcome-message h3 { margin: 16px 0 8px; }
.suggested-questions { margin-top: 20px; display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
.message-item { display: flex; gap: 12px; margin-bottom: 16px; padding: 0 8px; }
.message-item.user { flex-direction: row-reverse; }
.message-item.user .message-bubble { background: #409EFF; color: #fff; border-radius: 12px 2px 12px 12px; }
.message-bubble { max-width: 75%; padding: 12px 16px; background: #f4f4f5; border-radius: 2px 12px 12px 12px; font-size: 14px; line-height: 1.6; word-break: break-word; }
.message-bubble.thinking { background: #f4f4f5; }

/* Thinking Process */
.thinking-process { margin-bottom: 8px; }
.thinking-process :deep(.el-collapse) { border: none; }
.thinking-process :deep(.el-collapse-item__header) { height: 28px; line-height: 28px; background: transparent; border: none; font-size: 13px; color: #909399; }
.thinking-process :deep(.el-collapse-item__wrap) { border: none; background: transparent; }
.thinking-process :deep(.el-collapse-item__content) { padding-bottom: 0; }
.thinking-title { display: flex; align-items: center; gap: 4px; font-size: 13px; color: #909399; }
.thinking-detail { font-size: 13px; }
.thinking-step { margin-bottom: 8px; }
.step-label { font-weight: 600; color: #606266; font-size: 13px; }
.cypher-code { background: #f0f0f0; padding: 8px; border-radius: 4px; font-size: 12px; line-height: 1.5; overflow-x: auto; margin-top: 4px; color: #303133; }
.result-code { background: #f0f0f0; padding: 8px; border-radius: 4px; font-size: 12px; line-height: 1.5; overflow-x: auto; max-height: 200px; overflow-y: auto; margin-top: 4px; color: #606266; }

.md-content :deep(table) { border-collapse: collapse; width: 100%; margin: 8px 0; }
.md-content :deep(th), .md-content :deep(td) { border: 1px solid #e4e7ed; padding: 4px 8px; text-align: left; font-size: 13px; }
.md-content :deep(th) { background: #f5f7fa; }
.md-content :deep(code) { background: #f0f0f0; padding: 2px 4px; border-radius: 3px; font-size: 13px; }
.md-content :deep(pre) { background: #f0f0f0; padding: 12px; border-radius: 6px; overflow-x: auto; }
.message-meta { margin-top: 8px; display: flex; gap: 8px; align-items: center; }
.latency { font-size: 12px; color: #909399; }
.chat-input-area { padding: 16px 0; border-top: 1px solid #e4e7ed; }
.dot-animation::after { content: '...'; animation: dots 1.5s steps(3) infinite; }
@keyframes dots { 0% { content: '.'; } 33% { content: '..'; } 66% { content: '...'; } }

/* History Dialog */
.history-detail { margin-top: 16px; padding-top: 16px; border-top: 1px solid #e4e7ed; }
</style>
