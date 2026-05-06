# Auto Ontology Builder & QA System - 离线部署文档

## 系统概述

自动本体建模与知识图谱问答系统，支持从 Excel/CSV 数据自动构建本体、导入 Neo4j 知识图谱、智能问答。

### 技术栈
- **前端**: Vue 3 + TypeScript + Element Plus
- **后端**: FastAPI + SQLAlchemy (async) + OpenAI SDK
- **图数据库**: Neo4j 5.23 Community
- **部署**: 纯 Docker run（无需 docker-compose）

---

## 一、离线部署

### 1.1 前置条件

目标服务器需满足：
- Linux 系统（CentOS 7+ / Ubuntu 20.04+ / Debian 11+）
- 已安装 Docker Engine >= 20.10
- 至少 8GB 内存（Neo4j 需要 4G+1G pagecache）
- 磁盘空间 >= 5GB（用于镜像和数据）

**无需** docker-compose、无需外网。

### 1.2 上传部署包

将 `deploy/` 目录下的所有文件上传到目标服务器同一目录：

```
ontology-qa/
├── deploy.sh                    # 一键部署脚本
├── stop.sh                      # 停止并清理容器
├── status.sh                    # 查看运行状态
├── .env                         # 环境配置文件
├── neo4j-5.23-community.tar     # Neo4j 镜像 (487M)
├── ontology-qa-backend.tar      # 后端镜像 (520M)
├── ontology-qa-frontend.tar     # 前端镜像 (64M)
```

上传方式：SCP / SFTP / U盘拷贝均可。

```bash
# 在目标服务器上
mkdir -p /opt/ontology-qa
# 将文件上传到此目录（SCP示例）
# scp -r deploy/* user@target-server:/opt/ontology-qa/
```

### 1.3 修改配置

编辑 `.env` 文件，填入实际参数：

```bash
cd /opt/ontology-qa
vi .env
```

必须修改的配置：

```env
# Neo4j 密码
NEO4J_PASSWORD=your-secure-password

# LLM API Key（百炼/DeepSeek/OpenAI 任选一个）
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=http://your-llm-server/v1
LLM_MODEL_NAME=qwen-7b
```

可选修改的配置：

```env
# 数据持久化目录（默认 /opt/ontology-qa/data）
DATA_DIR=/data/ontology-qa
```

### 1.4 一键部署

```bash
cd /opt/ontology-qa
chmod +x deploy.sh stop.sh status.sh
./deploy.sh
```

部署脚本会自动执行：
1. 从 tar 文件导入 Docker 镜像
2. 创建 Docker 网络 `ontology-net`
3. 创建数据目录
4. 按顺序启动 Neo4j → Backend → Frontend
5. 自动等待 Neo4j 就绪后再启动后端

### 1.5 验证部署

```bash
# 查看状态
./status.sh

# 检查容器
docker ps

# 预期输出:
# ontology-frontend    RUNNING
# ontology-backend     RUNNING
# ontology-neo4j       RUNNING (healthy)

# 测试后端 API
curl http://localhost:8000/api/v1/system/health

# 预期: {"code": 200, "data": {"status": "healthy", ...}}
```

### 1.6 访问系统

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端界面 | `http://<服务器IP>:80` | 用户操作界面 |
| 后端 API | `http://<服务器IP>:8000` | RESTful API |
| Neo4j | `http://<服务器IP>:7474` | Neo4j Browser |

---

## 二、日常运维

### 2.1 查看状态

```bash
./status.sh
```

### 2.2 查看日志

```bash
# 后端日志
docker logs ontology-backend --tail 50 -f

# 前端日志
docker logs ontology-frontend --tail 50

# Neo4j 日志
docker logs ontology-neo4j --tail 50
```

### 2.3 停止服务

```bash
./stop.sh
```

### 2.4 重新启动

```bash
./stop.sh && ./deploy.sh
```

### 2.5 更新 LLM 配置

修改 `.env` 文件中的 LLM 配置后重启：

```bash
vi .env
docker restart ontology-backend
```

---

## 三、数据管理

### 3.1 数据位置

所有数据默认存储在 `${DATA_DIR}`（默认 `/opt/ontology-qa/data`）：

```
/opt/ontology-qa/data/
├── uploads/          # 用户上传的 Excel/CSV 文件
├── metadata.db       # SQLite 元数据（项目、数据源、本体定义）
└── neo4j/
    ├── data/         # Neo4j 图数据库
    └── logs/         # Neo4j 日志
```

### 3.2 备份数据

```bash
# 打包备份
tar czf ontology-qa-backup-$(date +%Y%m%d).tar.gz /opt/ontology-qa/data/
```

### 3.3 恢复数据

```bash
tar xzf ontology-qa-backup-YYYYMMDD.tar.gz -C /
./deploy.sh
```

---

## 四、LLM 配置说明

系统支持任何 OpenAI SDK 兼容的 LLM 接口。前端 "LLM 模型配置" 页面提供预设选项。

### 4.1 百炼（阿里云）

```env
LLM_BASE_URL=http://172.16.2.237:80/xlm-gateway-ypxikm/sfm-api-gateway/gateway/compatible-mode/v1
LLM_MODEL_NAME=qwen-7b
```

### 4.2 DeepSeek

```env
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL_NAME=deepseek-chat
```

### 4.3 其他兼容格式

只要是 `/v1/chat/completions` 兼容的接口均可使用。前端运行时可通过"LLM 配置"页面选择预设方案或自定义填写。

> **注意**：`.env` 中的配置是默认值，重启容器后生效。运行时通过前端页面修改的配置仅存于内存。

---

## 五、常见问题

### Q: Neo4j 启动很慢怎么办？

A: Neo4j 首次启动需要初始化数据库，可能需要 1-2 分钟。部署脚本会自动等待就绪。可以通过 `docker logs ontology-neo4j` 查看进度。

### Q: 内存不够怎么办？

A: 可以在 `.env` 中调整 Neo4j 内存参数（修改 `deploy.sh` 中的环境变量），建议至少 8GB RAM。

### Q: 如何更换 LLM 后端？

A: 修改 `.env` 中的 `LLM_BASE_URL`、`LLM_MODEL_NAME`、`LLM_API_KEY`，然后 `docker restart ontology-backend`。

### Q: 数据会丢失吗？

A: 不会。数据通过 Docker Volume 映射到宿主机的 `${DATA_DIR}` 目录，容器删除重建不影响数据。

---

## 六、开发机打包命令

在开发机上，完成代码修改后：

```bash
# 1. 构建最新镜像
docker compose build

# 2. 导出为 tar 文件
mkdir -p deploy
docker save ontology-qa-backend:latest -o deploy/ontology-qa-backend.tar
docker save ontology-qa-frontend:latest -o deploy/ontology-qa-frontend.tar
docker save neo4j:5.23-community -o deploy/neo4j-5.23-community.tar

# 3. 复制脚本和配置
cp deploy/deploy.sh deploy/
cp deploy/stop.sh deploy/
cp deploy/status.sh deploy/
cp deploy/.env deploy/

# 4. 整体打包（可选）
tar czf ontology-qa-deploy-$(date +%Y%m%d).tar.gz deploy/
```
