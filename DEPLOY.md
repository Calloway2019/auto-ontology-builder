# Auto Ontology Builder & QA System - 部署文档

## 系统概述

自动本体建模与知识图谱问答系统，支持从 Excel/CSV 数据自动构建本体、导入 Neo4j 知识图谱、智能问答。

### 技术栈
- **前端**: Vue 3 + TypeScript + Element Plus
- **后端**: FastAPI + SQLAlchemy (async) + OpenAI SDK
- **图数据库**: Neo4j 5.23 Community
- **部署**: Docker Compose

---

## 一、离线部署（Docker 镜像包）

### 1.1 前置条件

目标服务器需安装：
- Docker Engine >= 20.10
- Docker Compose V2 (docker compose 命令)

### 1.2 导入镜像

将以下 tar 文件复制到目标服务器：

```bash
# 导入镜像
docker load -i ontology-qa-backend.tar
docker load -i ontology-qa-frontend.tar
docker load -i neo4j-5.23-community.tar
```

### 1.3 准备配置文件

在部署目录创建 `docker-compose.yml` 和 `.env` 文件：

```bash
mkdir -p /opt/ontology-qa
cd /opt/ontology-qa
```

**docker-compose.yml:**

```yaml
name: ontology-qa

services:
  neo4j:
    image: neo4j:5.23-community
    container_name: ontology-neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: "neo4j/${NEO4J_PASSWORD:-ontology-qa-password}"
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_server_memory_heap_initial__size: "1G"
      NEO4J_server_memory_heap_max__size: "4G"
      NEO4J_server_memory_pagecache_size: "1G"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD:-ontology-qa-password}", "RETURN 1"]
      interval: 10s
      timeout: 10s
      retries: 5
      start_period: 30s
    networks:
      - ontology-net
    restart: unless-stopped

  backend:
    image: ontology-qa-backend:latest
    container_name: ontology-backend
    ports:
      - "8000:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=${NEO4J_USER:-neo4j}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD:-ontology-qa-password}
      - NEO4J_DATABASE=${NEO4J_DATABASE:-neo4j}
      - LLM_API_KEY=${LLM_API_KEY:-your-api-key-here}
      - LLM_BASE_URL=${LLM_BASE_URL:-http://172.16.2.237:80/xlm-gateway-ypxikm/sfm-api-gateway/gateway/compatible-mode/v1}
      - LLM_MODEL_NAME=${LLM_MODEL_NAME:-qwen-7b}
      - LLM_TEMPERATURE=${LLM_TEMPERATURE:-0.1}
      - LLM_MAX_TOKENS=${LLM_MAX_TOKENS:-4096}
      - LLM_TIMEOUT=${LLM_TIMEOUT:-120}
      - UPLOAD_DIR=/app/data/uploads
      - DATABASE_URL=sqlite:////app/data/metadata.db
      - DEBUG=${DEBUG:-false}
    volumes:
      - app_data:/app/data
    depends_on:
      neo4j:
        condition: service_healthy
    networks:
      - ontology-net
    restart: unless-stopped

  frontend:
    image: ontology-qa-frontend:latest
    container_name: ontology-frontend
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - ontology-net
    restart: unless-stopped

volumes:
  neo4j_data:
  neo4j_logs:
  app_data:

networks:
  ontology-net:
    driver: bridge
```

**.env 文件（按需修改）:**

```env
# Neo4j
NEO4J_PASSWORD=ontology-qa-password

# LLM - 百炼 (阿里云)
LLM_API_KEY=your-bailian-app-key
LLM_BASE_URL=http://172.16.2.237:80/xlm-gateway-ypxikm/sfm-api-gateway/gateway/compatible-mode/v1
LLM_MODEL_NAME=qwen-7b

# 如使用 DeepSeek，替换为：
# LLM_API_KEY=sk-xxx
# LLM_BASE_URL=https://api.deepseek.com/v1
# LLM_MODEL_NAME=deepseek-chat
```

### 1.4 启动服务

```bash
cd /opt/ontology-qa
docker compose up -d
```

### 1.5 验证部署

```bash
# 检查容器状态
docker compose ps

# 检查后端日志
docker compose logs backend --tail 20

# 验证 API
curl http://localhost:8000/api/v1/system/health
```

### 1.6 访问系统

| 服务 | 地址 |
|------|------|
| 前端界面 | http://<服务器IP>:80 |
| 后端 API | http://<服务器IP>:8000 |
| Neo4j Browser | http://<服务器IP>:7474 |

---

## 二、源码部署

### 2.1 克隆代码

```bash
git clone https://github.com/Calloway2019/auto-ontology-builder.git
cd auto-ontology-builder
```

### 2.2 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际的 LLM_API_KEY
```

### 2.3 构建并启动

```bash
docker compose build
docker compose up -d
```

---

## 三、LLM 配置说明

系统支持任何 OpenAI SDK 兼容的 LLM 接口。前端 "LLM 模型配置" 页面提供以下预设：

| 预设 | Base URL | 模型 |
|------|----------|------|
| 百炼（阿里云） | http://172.16.2.237:80/xlm-gateway-ypxikm/sfm-api-gateway/gateway/compatible-mode/v1 | qwen-7b |
| DeepSeek | https://api.deepseek.com/v1 | deepseek-chat |
| OpenAI | https://api.openai.com/v1 | gpt-4o |
| 自定义 | 用户自定义 | 用户自定义 |

**配置方式：**
1. 访问系统 → 左侧菜单 → "LLM 配置"
2. 选择预设方案或自定义填写
3. 输入 API Key
4. 点击"测试连接"验证
5. 点击"保存配置"

> 注意：运行时通过页面配置的 LLM 设置仅存于内存，重启后恢复为 .env / docker-compose.yml 中的默认值。如需永久修改请编辑 .env 文件后重启。

---

## 四、系统功能

1. **数据管理** - 上传 Excel/CSV 数据表 + 字段描述文本，LLM 自动匹配列含义
2. **本体构建** - 4 阶段 LLM 自动构建本体（Schema 分析 → 实体抽取 → 关系发现 → 校验优化）
3. **知识图谱** - 基于本体定义将数据导入 Neo4j，支持可视化浏览
4. **智能问答** - 自然语言提问 → LLM 生成 Cypher → Neo4j 查询 → LLM 合成回答

---

## 五、注意事项

1. **内存要求**: Neo4j 配置了 4G 堆内存 + 1G 页缓存，建议服务器至少 8G RAM
2. **图谱隔离**: 每个项目的图谱数据通过 `_project_id` 属性隔离，互不影响
3. **数据持久化**: Neo4j 数据和应用元数据通过 Docker Volume 持久化
4. **网络**: 前端通过 nginx 反向代理访问后端 API（/api 路由转发到 backend:8000）

---

## 六、打包镜像命令

在开发机上执行以下命令导出镜像：

```bash
# 构建最新镜像
docker compose build

# 导出为 tar 文件
docker save ontology-qa-backend:latest -o ontology-qa-backend.tar
docker save ontology-qa-frontend:latest -o ontology-qa-frontend.tar
docker save neo4j:5.23-community -o neo4j-5.23-community.tar
```

将三个 tar 文件以及 `docker-compose.yml` 和 `.env` 文件复制到目标机器即可部署。
