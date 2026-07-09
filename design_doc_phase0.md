# A股盯盘与复盘系统 — 设计文档

## 阶段 0：环境与基础设施

### 概述

本阶段旨在搭建完整的本地开发与运行环境，涵盖 WSL2 加速层、数据持久化中间件、后端/前端项目骨架以及 GPU 模型推理服务。所有组件全部运行在 Windows 11 + WSL2 + RTX 5080 的硬件加速底座上。

---

### T0.1 WSL2 环境配置

#### 目标

在 Windows 11 上启用 WSL2，安装 Ubuntu 22.04，配置 NVIDIA 驱动直通，使 WSL2 内可直接使用 RTX 5080 进行 GPU 计算。

#### 详细步骤

1. **启用 WSL2**
   - 以管理员身份打开 PowerShell，执行：
     ```powershell
     wsl --install -d Ubuntu-22.04
     ```
   - 确认 WSL 版本为 2：
     ```powershell
     wsl -l -v
     ```

2. **安装 NVIDIA 驱动 for WSL2**
   - 从 NVIDIA 官网下载并安装 [NVIDIA Driver for WSL2](https://developer.nvidia.com/cuda/wsl)（Game Ready 或 Studio 驱动均可）。
   - 驱动安装后，WSL2 内会自动继承 GPU 能力。

3. **验证 GPU 直通**
   - 进入 WSL2 终端：
     ```bash
     nvidia-smi
     ```
   - 预期输出：应能看到 RTX 5080 信息，CUDA Version ≥ 12.8。

   > ⚠️ **Blackwell 架构注意**：RTX 5080 / 5090 属 NVIDIA Blackwell（计算能力 12.0），
   > **必须 CUDA 12.8+ 与驱动 R570+** 才能启用 GPU。低于此版本的 CUDA / 驱动会导致
   > `torch.cuda.is_available()` 返回 False，模型全部退回到 CPU。

4. **安装 CUDA 工具链（WSL2 内）**
   ```bash
   # 安装 CUDA 12.8（Blackwell 最低要求，不要用 12.4）
   wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
   sudo dpkg -i cuda-keyring_1.1-1_all.deb
   sudo apt-get update
   sudo apt-get install -y cuda-toolkit-12-8
   ```

5. **安装 Python 与 PyTorch**
   ```bash
   sudo apt-get install -y python3-pip python3-venv
   # 必须用 cu128 轮子，cu124 不支持 Blackwell（sm_120）
   pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu128
   ```

6. **验收标准**
   ```bash
   python3 -c "import torch; print(torch.cuda.is_available())"
   # 必须返回 True
   python3 -c "import torch; print(torch.cuda.get_device_name(0))"
   # 应显示 "NVIDIA GeForce RTX 5080"
   ```

7. **WSL2 资源限制（非纯净系统适配）**
   在 `%USERPROFILE%\.wslconfig` 中添加以下配置，防止 WSL2 无限制占用系统资源：
   ```ini
   [wsl2]
   memory=24GB       # WSL2 最大使用 24GB，Windows 保底 24GB
   processors=8      # 分配 8 核，利用 9800X3D 全 16 线程并行为盘后因子计算、FinBERT 推理、新闻翻译留足算力
   swap=4GB          # 备用 swap 防止 OOM
   ```
   配置生效方式：
   ```powershell
   wsl --shutdown
   wsl
   ```
   > 注意：`memory` 是硬上限而非独占，Windows 空闲时 WSL2 仍可超卖。`processors` 默认 8（盘后并行任务多，4 核易成瓶颈）；**若日常使用感到系统卡顿，可临时降到 4–6**，选股查询等计算密集型任务才不会拖慢桌面操作。

#### 架构图

```
┌─────────────────────────────────────────────────────┐
│                  Windows 11 Host                     │
│  ┌──────────────────────────────────────────────┐   │
│  │              WSL2 (Ubuntu 22.04)              │   │
│  │  ┌──────────────────────────────────────┐    │   │
│  │  │     NVIDIA Driver (直通)              │    │   │
│  │  │         RTX 5080 (16GB VRAM)          │    │   │
│  │  └──────────────────────────────────────┘    │   │
│  │  • CUDA 12.8  • PyTorch  • Ollama           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

### T0.2 数据库与中间件部署

#### 目标

使用 Docker Compose 在 WSL2 内启动 TimescaleDB、Redis，配置 Windows 挂载目录实现数据持久化。

#### 组件选型

| 组件 | 用途 | 替代方案 | 选型理由 |
|------|------|----------|----------|
| **TimescaleDB** | 行情时序数据存储 | MongoDB（PG JSONB 替代） | 原生 SQL + 时序分区，支持复杂聚合查询 |
| **Redis** | 缓存 / 实时消息 / Celery Broker | — | 成熟、轻量，生态完善 |

#### 目录结构

```
d:\code\project\trading_tools\docker\
├── docker-compose.yml
├── timescale/
│   └── init.sql              # 首次初始化脚本
└── redis/
    └── redis.conf            # Redis 配置文件
```

#### docker-compose.yml

- **TimescaleDB**: 端口 5432，挂载 `d:\code\project\trading_tools\data\timescale` → WSL2 `/var/lib/postgresql/data`
- **Redis**: 端口 6379，挂载 `d:\code\project\trading_tools\data\redis` → WSL2 `/data`

#### PostgreSQL 内存配置（非纯净系统适配）

由于系统非纯净，WSL2 实际可用内存约 24GB，PostgreSQL 参数需保守设定：

```ini
# docker/timescale/postgresql.conf (额外挂载)
shared_buffers = 4GB              # PG 自身缓存
effective_cache_size = 8GB        # 告知 PG 系统缓存约 8GB（保守，不跟 Redis/Ollama 抢）
work_mem = 64MB                   # 排序/哈希操作内存（避免单查询撑爆）
maintenance_work_mem = 512MB      # VACUUM/建索引专用
```

此配置在全市场因子查询场景下足够，且不会与 Ollama、Redis 等抢内存。

#### 验收标准

```bash
docker ps
# 确认 timescale 和 redis 状态为 healthy 或 Up

# TimescaleDB 连接测试
psql -h localhost -U postgres -d trading -c "SELECT extname FROM pg_extension WHERE extname='timescaledb';"
# 应返回 timescaledb

# Redis 连接测试
redis-cli ping
# 应返回 PONG
```

---

### T0.3 后端项目骨架搭建

#### 目标

使用 Poetry 初始化 Python 项目，安装核心依赖，创建标准分层目录结构，启动 Uvicorn 可访问 Swagger 文档。

#### 技术栈

| 框架/库 | 版本 | 用途 |
|----------|------|------|
| Python | ≥ 3.11 | 运行时 |
| FastAPI | ≥ 0.110 | HTTP API 框架 |
| SQLAlchemy | ≥ 2.0 | ORM |
| asyncpg | ≥ 0.29 | 异步 PG 驱动 |
| Celery | ≥ 5.3 | 异步任务队列 |
| Redis (redis-py) | ≥ 5.0 | 缓存 / Broker |
| websockets | ≥ 12.0 | 实时行情推送 |
| pandas | ≥ 2.2 | 数据处理 |
| numpy | ≥ 1.26 | 数值计算 |
| akshare | ≥ 1.14 | A股数据源 |
| loguru | ≥ 0.7 | 日志 |
| pydantic | ≥ 2.6 | 数据校验 |
| httpx | ≥ 0.27 | HTTP 客户端 |
| alembic | ≥ 1.13 | 数据库迁移 |

#### 目录结构

```
backend/
├── pyproject.toml
├── poetry.lock
├── alembic.ini
├── alembic/
│   └── versions/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 全局配置（环境变量读取）
│   ├── api/                     # 路由层
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── market.py        # 行情接口
│   │   │   ├── stock.py         # 个股接口
│   │   │   └── analysis.py      # 分析接口
│   │   └── deps.py              # 依赖注入（DB session 等）
│   ├── core/                    # 核心模块
│   │   ├── __init__.py
│   │   ├── database.py          # SQLAlchemy 引擎与会话
│   │   ├── redis_client.py      # Redis 客户端
│   │   ├── celery_app.py        # Celery 应用
│   │   └── security.py          # JWT / 认证工具
│   ├── models/                  # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── stock.py             # 股票基本信息
│   │   ├── kline.py             # K 线数据（TimescaleDB hypertable）
│   │   └── user.py              # 用户/持仓
│   ├── services/                # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── market_service.py    # 行情服务
│   │   ├── analysis_service.py  # 分析服务
│   │   └── llm_service.py       # LLM 调用服务
│   ├── tasks/                   # Celery 异步任务
│   │   ├── __init__.py
│   │   ├── data_collect.py      # 数据采集任务
│   │   └── analysis_tasks.py    # 分析计算任务
│   └── schemas/                 # Pydantic 模型（API 请求/响应）
│       ├── __init__.py
│       ├── market.py
│       └── stock.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_api/
    └── test_services/
```

#### 验收标准

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# 浏览器访问 http://localhost:8000/docs 应显示 Swagger 界面
```

---

### T0.4 前端项目骨架搭建

#### 目标

使用 Vite 创建 React 18 + TypeScript 项目，集成 UI 与图表组件库，配置路由系统。

#### 技术栈

| 框架/库 | 版本 | 用途 |
|----------|------|------|
| React | ≥ 18.3 | UI 框架 |
| TypeScript | ≥ 5.4 | 类型安全 |
| Vite | ≥ 5.2 | 构建工具 |
| Ant Design | ≥ 5.15 | UI 组件库 |
| ECharts (echarts-for-react) | ≥ 5.5 | 图表 |
| KLineChart | 9.5.x（pin 具体版本） | 专业 K 线图（**注意 v9 与 v8 API 差异很大，务必锁定主版本**） |
| Zustand | ≥ 4.5 | 状态管理 |
| React Router | ≥ 6.22 | 路由 |
| Axios | ≥ 1.6 | HTTP 请求 |

#### 目录结构

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx                # 入口
    ├── App.tsx                 # 路由配置
    ├── vite-env.d.ts
    ├── layouts/
    │   ├── MainLayout.tsx      # 主布局（侧边栏 + 内容区）
    │   └── components/
    │       ├── Sidebar.tsx
    │       └── Header.tsx
    ├── pages/
    │   ├── Dashboard/          # 仪表盘 / 盯盘
    │   │   └── index.tsx
    │   ├── StockPicker/        # 选股
    │   │   └── index.tsx
    │   ├── Report/             # 复盘报告
    │   │   └── index.tsx
    │   ├── Risk/               # 风控
    │   │   └── index.tsx
    │   └── NotFound/
    │       └── index.tsx
    ├── components/             # 共享组件
    │   ├── KLineChart/
    │   │   └── index.tsx
    │   └── StockTable/
    │       └── index.tsx
    ├── stores/                 # Zustand 状态
    │   ├── useMarketStore.ts
    │   └── useUserStore.ts
    ├── services/               # API 调用
    │   └── api.ts
    └── utils/
        └── format.ts
```

#### 路由设计

| 路径 | 页面 | 描述 |
|------|------|------|
| `/` | Dashboard | 盯盘仪表盘，实时行情 |
| `/stock-picker` | StockPicker | 选股策略 |
| `/report` | Report | 复盘报告 |
| `/risk` | Risk | 风控监控 |
| `*` | NotFound | 404 |

#### 验收标准

```bash
cd frontend
npm install
npm run dev
# 浏览器访问 http://localhost:5173 应看到主布局（侧边栏导航 + 内容区）
# 点击路由导航应能切换页面
```

---

### T0.5 GPU 模型服务部署

#### 目标

在 WSL2 中部署本地大语言模型，通过 REST API 提供自然语言分析与解释能力。

#### 模型选型

| 模型 | 用途 | 推荐版本 |
|------|------|----------|
| **Qwen2.5 14B** | 盘后深度复盘、趋势分析 | `qwen2.5:14b-instruct-q4_K_M`（约 9–10GB VRAM） |
| **Qwen2.5 3B** | 盘中轻量解释、快速问答 | `qwen2.5:3b-instruct-q4_K_M`（约 2GB VRAM） |

> ⚠️ **显存预算（RTX 5080 = 16GB）**：Qwen2.5-14B q4_K_M 实际约 **9–10GB**，3B 约 2GB，FinBERT-zh 约 1.5GB，三者同驻合计约 **12.5GB**，16GB 显存仅剩 ~3.5GB 给 KV cache 与系统，**余量非常紧张**。建议用 Ollama 的 `keep_alive` 控制低频模型（3B / FinBERT）用完即卸载；报告生成与盘中对话尽量错峰，避免并发占满显存触发 OOM。

#### 部署方案：Ollama

1. **安装 Ollama**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **拉取模型**
   ```bash
   ollama pull qwen2.5:14b-instruct-q4_K_M
   ollama pull qwen2.5:3b-instruct-q4_K_M
   ```

3. **配置为系统服务**
   ```bash
   # Ollama 安装后自动注册为 systemd 服务
   sudo systemctl enable ollama
   sudo systemctl start ollama
   ```

4. **验证 API**
   ```bash
   curl http://localhost:11434/api/generate \
     -d '{"model": "qwen2.5:3b-instruct-q4_K_M", "prompt": "简述今日A股市场概况", "stream": false}'
   ```

#### 调用封装（后端 service）

在 `backend/app/services/llm_service.py` 中封装统一调用接口：

```python
class LLMService:
    """大模型调用服务，封装 Ollama REST API"""

    OLLAMA_BASE_URL = "http://localhost:11434"

    @staticmethod
    async def generate(
        prompt: str,
        model: str = "qwen2.5:14b-instruct-q4_K_M",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """调用 LLM 生成文本"""
        ...

    @staticmethod
    async def stream_generate(
        prompt: str,
        model: str = "qwen2.5:3b-instruct-q4_K_M",
    ) -> AsyncIterator[str]:
        """流式生成（用于盘中等候快速响应）"""
        ...
```

#### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    WSL2 (Ubuntu 22.04)                      │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────────────────┐   │
│  │    Ollama         │    │    FastAPI Backend            │   │
│  │  ┌────────────┐   │    │  ┌────────────────────────┐  │   │
│  │  │ Qwen 14B   │◄──┼────┼──┤ LLMService.py          │  │   │
│  │  │ (~9GB VRAM) │   │    │  │ • generate()           │  │   │
│  │  ├────────────┤   │    │  │ • stream_generate()    │  │   │
│  │  │ Qwen 3B    │   │    │  └────────────────────────┘  │   │
│  │  │ (2GB VRAM) │   │    └──────────────────────────────┘   │
│  │  └────────────┘   │                                       │
│  │  Port: 11434      │                                       │
│  └──────────────────┘                                        │
│                                                             │
│  ┌──────────────────────────────────┐                       │
│  │        RTX 5080 (16GB)           │                       │
│  │  ~11GB used (14B 9 + 3B 2) ← FinBERT 另占 1.5GB，余量紧张 │                       │
│  └──────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

### 阶段 0 整体架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Windows 11 Host (48GB RAM / 8核)              │
│                                                                      │
│  WSL2 (Ubuntu 22.04) ← memory=24GB, processors=8 ──────────────┐  │
│  ┌────────────────────────────────────────────────────────────┐   │  │
│  │  Docker Containers + 原生进程混合                             │   │  │
│  │  ┌─────────────┐  ┌──────────┐  ┌────────────────────────┐ │   │  │
│  │  │ TimescaleDB │  │  Redis   │  │  Ollama (WSL2 原生,    │ │   │  │
│  │  │  :5432      │  │  :6379   │  │  避开 Docker GPU 开销)  │ │   │  │
│  │  └─────────────┘  └──────────┘  └────────────────────────┘ │   │  │
│  │  ┌─────────────────┐  ┌──────────────────────────────┐     │   │  │
│  │  │ FastAPI Backend  │  │  Celery Worker              │     │   │  │
│  │  │  :8000           │  │  (充分利用 4 核并行计算)     │     │   │  │
│  │  └─────────────────┘  └──────────────────────────────┘     │   │  │
│  └────────────────────────────────────────────────────────────┘   │  │
│                                                                    │  │
│  ┌────────────────────────────────────────────────────────────┐   │  │
│  │              RTX 5080 (CUDA 12.8) — 实际可用 ~16GB VRAM    │   │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │   │  │
│  │  │ Qwen2.5-14B  │  │ Qwen2.5-3B   │  │ FinBERT-zh       │ │   │  │
│  │  │ (~9GB VRAM)   │  │ (2GB VRAM)   │  │ (1.5GB VRAM)     │ │   │  │
│  │  │ 复盘/选股解释 │  │ 盘中快问/    │  │ 新闻情感分类     │ │   │  │
│  │  │ AI 对话       │  │ 零样本分类   │  │                  │ │   │  │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘ │   │  │
│  │  总计 ~12.5GB（14B 9 + 3B 2 + FinBERT 1.5），16GB 显存剩 ~3.5GB，KV cache 紧张；低频模型用完即卸载 │   │  │
│  └────────────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘      │
│                                                                      │
│  Host ─────────────────────────────────────────────────────────┐    │
│  │  Frontend (Vite + React) — 直接跑在 Windows 上 :5173        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

#### 混合部署方案说明（省内存推荐）

非纯净系统下，所有服务塞进 Docker 可能造成资源竞争。推荐按以下策略分摊：

| 服务 | 部署方式 | 理由 |
|------|----------|------|
| **TimescaleDB** | Docker (WSL2) | 稳定持久化，容器化管理 |
| **Redis** | Docker (WSL2) | 轻量无压力 |
| **Ollama (Qwen/FinBERT)** | WSL2 **原生** | 避免 Docker GPU 映射开销，GPU 调用更直接 |
| **FastAPI + Celery** | WSL2 原生 或 Windows 原生 | 可使用 48GB 主机全量内存，不受 WSL2 memory 限制 |
| **Frontend** | Windows 原生 | Vite 开发更流畅，直接访问 Windows 文件系统 |

> 如果 WSL2 24GB 配额足够，FastAPI/Celery 也放 WSL2 原生最省事。仅当 OOM 时需切到 Windows 原生运行后端。

#### 统一配置管理

随着混合部署和参数增多，配置集中为 `backend/config.yaml` + `.env`：

```yaml
# backend/config.yaml
wsl2:
  memory_gb: 24
  processors: 8

database:
  postgres:
    host: localhost
    port: 5432
    shared_buffers: 4GB
    effective_cache_size: 8GB
    work_mem: 64MB
  duckdb:
    temp_directory: /tmp/duckdb
    memory_limit: 2GB        # DuckDB 最大内存，不与 PG/Ollama 抢
  redis:
    host: localhost
    port: 6379

llm:
  ollama_base_url: http://localhost:11434
  report_model: qwen2.5:14b-instruct-q4_K_M
  chat_model: qwen2.5:3b-instruct-q4_K_M
  finbert_model: models/finbert-zh

news:
  overseas_enabled: false          # V1.0 关闭，V1.1 开启
  crawl_frequency_min:
    cls: 10
    eastmoney: 15
    xueqiu: 30
```

```bash
# .env（敏感信息）
TUSHARE_TOKEN=your_token
SMTP_PASSWORD=xxx
```

配置加载优先级：环境变量 > `config.yaml` > 默认值。

---

### 依赖关系与并行策略

```
T0.1 WSL2 ─────┬──── T0.2 Docker Compose ──── T0.3 Backend
                │
                └──── T0.5 Ollama

T0.4 Frontend（无依赖，可与 T0.1/T0.2/T0.3/T0.5 并行执行）
```

| 任务 | 预估工时 | 可并行 |
|------|----------|--------|
| T0.1 WSL2 环境配置 | 2h | — |
| T0.2 数据库与中间件 | 2h | 否（依赖 T0.1） |
| T0.3 后端骨架 | 2h | 否（依赖 T0.2） |
| T0.4 前端骨架 | 2h | **是（完全并行）** |
| T0.5 GPU 模型服务 | 1h | 否（依赖 T0.1） |
| **阶段合计** | **~9h（实际约 5h 并行后）** | |

---

### 验收清单汇总

| 编号 | 验收项 | 命令/操作 |
|------|--------|-----------|
| 0.1 | GPU 可用 | `python3 -c "import torch; print(torch.cuda.is_available())"` → True（CUDA 12.8+） |
| 0.2 | TimescaleDB 可用 | `psql` 连接 + `\dx` 看到 timescaledb |
| 0.3 | Redis 可用 | `redis-cli ping` → PONG |
| 0.4 | FastAPI Swagger | 浏览器 `http://localhost:8000/docs` |
| 0.5 | 前端页面 | 浏览器 `http://localhost:5173` 看到布局 |
| 0.6 | LLM 推理 | `curl` 调用 Ollama API 返回自然语言 |

---

## 阶段 1：MVP — 行情看板与实时推送

### 概述

本阶段实现 MVP 核心链路：数据源采集 → TimescaleDB 存储 → 实时行情网关 → WebSocket 推送 → 前端 Dashboard 展示。目标准时：打开页面 3 秒内看到实时 K 线和自选股价格跳动。

### 数据流架构

```
东方财富 / Tushare         FastAPI Backend               Frontend
     │                         │                            │
     ▼                         ▼                            ▼
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Data Source │───▶│  QuoteProvider   │───▶│   WebSocket Server  │───▶ Dashboard
│  (HTTP/WS)    │    │  (适配器层)       │    │   /ws/market        │    (实时更新)
└─────────────┘    └───────┬──────────┘    └─────────────────────┘
                           │                          ▲
                           ▼                          │
                    ┌──────────────┐         ┌────────────────┐
                    │ TimescaleDB  │         │   Redis Stream │
                    │ (历史K线)     │         │ (实时行情管道)  │
                    └──────────────┘         └────────────────┘
```

---

### T1.1 数据源适配层

#### 目标

实现统一的数据源适配层，支持 Tushare Pro 和 AkShare 两种数据源，为上层提供一致的历史 K 线和实时行情接口。

#### 设计

**QuoteProvider 基类接口**

```python
from abc import ABC, abstractmethod
import pandas as pd
from datetime import date

class QuoteProvider(ABC):
    """行情数据提供者基类，所有数据源需实现此接口"""

    @abstractmethod
    async def get_daily_kline(
        self, symbol: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """获取日K线数据"""
        ...

    @abstractmethod
    async def get_minute_kline(
        self, symbol: str, trade_date: date
    ) -> pd.DataFrame:
        """获取分钟K线数据"""
        ...

    @abstractmethod
    async def get_realtime_quote(
        self, symbol: str
    ) -> dict:
        """获取实时行情快照"""
        ...
```

**返回 DataFrame 标准字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | str | 股票代码，如 `000001.SZ` |
| `trade_date` / `trade_time` | datetime | 交易时间 |
| `open` | float | 开盘价 |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `close` | float | 收盘价/最新价 |
| `volume` | int | 成交量（股） |
| `amount` | float | 成交额（元） |

#### 目录结构

```
backend/app/services/data_providers/
├── __init__.py
├── base.py                    # QuoteProvider 抽象基类
├── tushare.py                 # Tushare Pro 实现
└── akshare.py                 # AkShare 实现
```

#### 配置管理（.env）

```
# .env
TUSHARE_TOKEN=your_token_here
DATA_PROVIDER_DEFAULT=akshare    # 默认数据源：akshare / tushare
```

#### 验收标准

```python
# 单元测试可验证
# 1. 平安银行（000001.SZ）近5日日K线
provider = AkShareProvider()
df = await provider.get_daily_kline("000001.SZ", "2024-01-01", "2024-01-10")
assert len(df) > 0
assert all(c in df.columns for c in ["open", "high", "low", "close", "volume"])

# 2. 平安银行实时价
quote = await provider.get_realtime_quote("000001.SZ")
assert "price" in quote and "volume" in quote
```

---

### T1.2 TimescaleDB K 线表设计与历史数据入库

#### 目标

设计时序超表存储日 K 和分钟 K，配置自动压缩策略，编写全市场历史数据同步脚本。

#### 表结构设计

```sql
-- 日K线超表
CREATE TABLE stock_daily (
    symbol     TEXT        NOT NULL,   -- 股票代码，如 000001.SZ
    trade_date TIMESTAMPTZ NOT NULL,   -- 交易日
    open       NUMERIC(10,2),
    high       NUMERIC(10,2),
    low        NUMERIC(10,2),
    close      NUMERIC(10,2),
    pre_close  NUMERIC(10,2),
    volume     BIGINT,                 -- 成交量（股）
    amount     NUMERIC(16,2),          -- 成交额（元）
    amplitude  NUMERIC(5,2),           -- 振幅 %
    pct_change NUMERIC(5,2),           -- 涨跌幅 %
    turn       NUMERIC(6,4),           -- 换手率
    PRIMARY KEY (symbol, trade_date)
);

-- 转换为超表，按 trade_date 排序（日 K 用 3 个月一个 chunk，避免 7 天过碎产生大量 chunk）
SELECT create_hypertable('stock_daily', 'trade_date',
    chunk_time_interval => INTERVAL '3 months',
    if_not_exists => TRUE
);

-- 配置压缩策略：30天前的数据自动压缩
ALTER TABLE stock_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);
SELECT add_compression_policy('stock_daily', INTERVAL '30 days');

-- （可选）物化视图：每日涨幅榜 / 板块热力等看板常用聚合，用连续聚合预计算，减少重复全表扫描
CREATE MATERIALIZED VIEW mv_daily_summary
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 day', trade_date) AS day,
       count(*) FILTER (WHERE pct_change > 0)  AS up_count,
       count(*) FILTER (WHERE pct_change < 0)  AS down_count
FROM stock_daily
GROUP BY day;

-- ⚠️ 时区：trade_date 用 TIMESTAMPTZ 存储（UTC）。A 股按 Asia/Shanghai，
--    日期过滤（如 WHERE trade_date = '2026-06-04'）若 PG 会话时区是 UTC 会产生 ±1 天偏移。
--    建议统一设置会话时区：SET TIME ZONE 'Asia/Shanghai'; 或后续将 trade_date 改为 DATE 类型。


-- 分钟K线超表
CREATE TABLE stock_minute (
    symbol      TEXT           NOT NULL,
    trade_time  TIMESTAMPTZ    NOT NULL,
    open        NUMERIC(10,2),
    high        NUMERIC(10,2),
    low         NUMERIC(10,2),
    close       NUMERIC(10,2),
    volume      BIGINT,
    amount      NUMERIC(16,2),
    PRIMARY KEY (symbol, trade_time)
);

SELECT create_hypertable('stock_minute', 'trade_time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

ALTER TABLE stock_minute SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);
SELECT add_compression_policy('stock_minute', INTERVAL '7 days');
```

#### ORM 模型映射

```python
# backend/app/models/timescale.py
from sqlalchemy import Column, String, Numeric, BigInteger, DateTime
from app.core.database import Base

class StockDaily(Base):
    """日K线模型，映射 stock_daily 超表"""
    __tablename__ = "stock_daily"

    symbol     = Column(String(16), primary_key=True)
    trade_date = Column(DateTime(timezone=True), primary_key=True)
    open       = Column(Numeric(10, 2))
    high       = Column(Numeric(10, 2))
    low        = Column(Numeric(10, 2))
    close      = Column(Numeric(10, 2))
    pre_close  = Column(Numeric(10, 2))
    volume     = Column(BigInteger)
    amount     = Column(Numeric(16, 2))
    amplitude  = Column(Numeric(5, 2))
    pct_change = Column(Numeric(5, 2))
    turn       = Column(Numeric(6, 4))


class StockMinute(Base):
    """分钟K线模型，映射 stock_minute 超表"""
    __tablename__ = "stock_minute"

    symbol     = Column(String(16), primary_key=True)
    trade_time = Column(DateTime(timezone=True), primary_key=True)
    open       = Column(Numeric(10, 2))
    high       = Column(Numeric(10, 2))
    low        = Column(Numeric(10, 2))
    close      = Column(Numeric(10, 2))
    volume     = Column(BigInteger)
    amount     = Column(Numeric(16, 2))
```

#### 全量同步脚本

```
scripts/
└── sync_history.py    # A股全市场近5年日K同步脚本
```

**脚本逻辑**

```
1. 从数据源获取全市场股票列表（约 5000+ 只）
2. 按批次（每批 100 只）并发拉取日K线
3. 使用 COPY/batch insert 写入 TimescaleDB
4. 输出进度日志：processed: 500/5000, failed: 2
```

#### 验收标准

```sql
SELECT count(*) FROM stock_daily;
-- 预期 >= 5000 * 1200 ≈ 600 万条
```

---

### T1.3 实时行情网关（QuoteGateway）

#### 目标

构建协程驱动的实时行情网关，从数据源接收实时流，标准化后推送到 Redis Stream，同时提供 REST 查询接口。

#### 设计

> **数据源现实约束**：A 股实时行情**没有公开的标准 WebSocket 推送**。AkShare 的东方财富实时行情底层是**东方财富 push2 的 SSE / HTTP 轮询接口**；Tushare 个人版实时行情也是 **HTTP 限频拉取（需积分）**，无公开推送 WS。因此 QuoteGateway 以**轮询 / SSE 长连**方式从 AkShare 拉取，解码标准化后写入 Redis Stream，而非"直接从 WS 接收实时流"。

```
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  Data Source     │     │   QuoteGateway        │     │   Redis Stream   │
│  东方财富 push2  │────▶│   (asyncio 协程)       │────▶│  "QUOTE_STREAM"  │
│  (SSE / 轮询)    │     │                      │     │                  │
│  Tushare(HTTP限频)│    │                      │     │                  │
└─────────────────┘     │ • 轮询 / SSE 拉取     │     │ • 消费者: WS推送  │
                        │ • 协议转换 / 标准化    │     │ • 消费者: 异动检测│
                        │ • 心跳检测             │     └──────────────────┘
                        │ • 自动重连 / 限流退避  │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────┐
                        │  REST API         │
                        │  GET /api/v1/quote│
                        │  /{symbol}       │
                        └──────────────────┘
```

> **轮询频率建议**：仅对自选股 / 持仓（数十~数百只）做 1–3 秒级轮询；全市场 5000+ 只只做盘后批量入库，盘中不要轮询全市场，否则易被接口限流 / 封 IP。

#### 标准消息格式

```json
{
  "symbol": "000001.SZ",
  "name": "平安银行",
  "timestamp": "2026-06-04T09:30:05.000Z",
  "price": 11.25,
  "open": 11.10,
  "high": 11.30,
  "low": 11.08,
  "pre_close": 11.00,
  "volume": 1523000,
  "amount": 17133750.00,
  "pct_change": 2.27,
  "bid_price": 11.24,
  "ask_price": 11.25,
  "bid_volume": 1000,
  "ask_volume": 2000
}
```

#### 文件清单

```
backend/app/services/quote_gateway.py    # 行情网关主逻辑
backend/app/services/redis_stream.py     # Redis Stream 工具封装
```

#### 多进程改造（可选优化）

默认使用单进程协程即可满足盘中使用。如需更高吞吐量，可配置多进程模式：

```python
# config.py
QUOTE_GATEWAY_MODE = "single"       # single | multi
QUOTE_GATEWAY_WORKERS = 2           # multi 模式下的进程数（建议 2，避免拖慢系统）
```

```diff
- 默认单进程协程（9800X3D 一个核就够行情解码）
+ 可选 2-4 进程，通过 multiprocessing.Queue 或 ZeroMQ 做进程间通信
+ 非纯净系统建议保持单进程，吃不满网速的
```

#### 验收标准

```bash
# 1. Redis Stream 接收验证
redis-cli XREAD COUNT 10 STREAMS QUOTE_STREAM 0
# 应看到实时行情消息

# 2. REST API 验证
curl http://localhost:8000/api/v1/quote/000001.SZ
# 返回最新行情 JSON
```

---

### T1.4 WebSocket 行情推送服务

#### 目标

实现 WebSocket 端点，支持用户订阅/取消订阅自选股实时行情，集成简单异动检测（涨跌幅 > 3% 触发推送标识）。

#### 协议设计

```json
// 客户端 → 服务端（订阅）
{
  "type": "subscribe",
  "symbols": ["000001.SZ", "600519.SH"]
}

// 客户端 → 服务端（取消订阅）
{
  "type": "unsubscribe",
  "symbols": ["000001.SZ"]
}

// 服务端 → 客户端（行情推送）
{
  "type": "quote",
  "data": {
    "symbol": "000001.SZ",
    "price": 11.25,
    "pct_change": 2.27,
    "timestamp": "2026-06-04T09:30:05.000Z"
  }
}

// 服务端 → 客户端（异动告警）
{
  "type": "alert",
  "data": {
    "symbol": "000001.SZ",
    "reason": "涨跌幅超3%",
    "pct_change": 3.15
  }
}
```

#### 后端实现

```
backend/app/api/v1/ws.py    # WebSocket 端点
```

**核心逻辑**

```
1. 客户端连接 → 建立 WebSocket 连接
2. 接收 subscribe → 将连接加入进程内「symbol → 连接集合」订阅表（不是各自消费流）
3. **单一全局消费者协程**持续从 Redis Stream（或 Redis Pub/Sub）消费行情，
   一次读取即广播给所有订阅该 symbol 的连接，避免 N 个连接重复消费 N 倍流量
4. 每个连接按自身订阅集合过滤后推送
5. 异动检测：pct_change > 3% 时附带 alert 标记
6. 断开连接 → 从订阅表移除
```

> **扩展说明（支撑 T4.5 的「100+ 并发」目标）**：行情扇出推荐用 **Redis Pub/Sub**（天然一对多广播），而非 Stream 消费者组；若沿用 Stream，则只设一个 `ws_push` 消费者做全局广播，连接级只做内存过滤。否则每多一个连接就多一份全量流的重复读取，并发上不去。

#### 前端 hooks

```
frontend/src/hooks/
└── useWebSocket.ts          # WebSocket 连接管理 Hook
```

**Hook 接口**

```typescript
interface UseWebSocketReturn {
  quotes: Map<string, Quote>;        // 实时行情映射
  alerts: Alert[];                   // 异动列表
  subscribe: (symbols: string[]) => void;
  unsubscribe: (symbols: string[]) => void;
  isConnected: boolean;
}

function useWebSocket(): UseWebSocketReturn;
```

#### 验收标准

- 前端连接 WebSocket 后，自选股列表价格每 2-3 秒自动刷新
- 涨跌幅超 3% 时前端收到异动标识

---

### T1.5 盯盘大盘页（前端）

#### 目标

实现首页 Dashboard，提供实时大盘指数、板块热力图、自选股价格表和涨幅榜。

#### 页面布局

```
┌──────────────────────────────────────────────────────────┐
│  上证指数   深证成指   创业板指   科创50                   │  ← 指数卡片
│  3200.50   10200.30   2150.80    980.60                  │
│  +0.85%    +1.20%     -0.35%    +0.52%                  │
├──────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │    板块热力图         │  │    自选股 (可分组)       │ │
│  │  (ECharts 矩形树图)   │  │  ┌─── 分组切换 ────┐   │ │
│  │                      │  │  │ [核心持仓] [观察]│   │ │
│  │ 银行 ████████        │  │  ├──────────────────┤   │ │
│  │ 证券 ██████          │  │  │ 平安银行  11.25   │   │ │
│  │ 医药 ████            │  │  │ 贵州茅台 1580.00  │   │ │
│  │ 科技 ██████████      │  │  │ 宁德时代 210.50   │   │ │
│  │                      │  │  │ 添加分组 [+]     │   │ │
│  └──────────────────────┘  │  └──────────────────┘   │ │
│                            └──────────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│  涨幅榜                                                    │
│  ┌──────┬────────┬────────┬────────┬──────────────────┐ │
│  │ 代码  │ 名称   │ 最新价 │ 涨幅   │ 成交额           │ │
│  │ 600XXX│ XXXXX  │ 12.34 │ +10.00%│ 1.2亿            │ │
│  └──────┴────────┴────────┴────────┴──────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

#### 文件清单

```
frontend/src/pages/Dashboard/
├── index.tsx                    # 页面入口，组合各组件
├── components/
│   ├── IndexCard.tsx            # 指数卡片（上证/深证/创业板/科创50）
│   ├── SectorHeatmap.tsx        # 板块热力图（ECharts 矩形树图）
│   ├── WatchlistTable.tsx       # 自选股实时价格表
│   └── TopGainers.tsx           # 涨幅榜
├── hooks/
│   └── useDashboard.ts          # Dashboard 数据聚合 Hook
```

#### 验收标准

- 打开 Dashboard 页面 3 秒内看到数据渲染
- 指数卡片、自选股价格通过 WebSocket 自动更新
- 涨幅榜每分钟刷新

---

### T1.6 MVP 集成测试

#### 目标

验证完整数据链路（数据源 → 入库 → 网关 → WebSocket → 前端）正常运行，处理断线重连和边界情况。

#### 测试范围

| 测试项 | 描述 | 方法 |
|--------|------|------|
| 链路完整性 | 数据从源头到前端展示全链路可达 | 启动所有服务，前端观察数据更新 |
| 断线重连 | WebSocket 断开后自动重连，不丢数据 | 手动重启后端，观察前端自动恢复 |
| 空数据容错 | 停牌股票、节假日无行情 | 查询停牌股票，前端显示"暂停交易" |
| Redis 故障恢复 | Redis 重启后网关自动恢复 | 重启 Redis 容器，观察网关重连 |
| 并发订阅 | 多用户连接 WebSocket | 开多个浏览器标签页同时订阅 |

#### 产出

- 测试报告（记录测试项、通过/失败、问题描述）
- Bug 修复

---

### 阶段 1 整体架构与数据流

```
                          ┌─────────────────────┐
                          │     Frontend         │
                          │  :5173               │
                          │  ┌───────────────┐   │
                          │  │  Dashboard    │   │
                          │  │  • 指数卡片    │   │
                          │  │  • 板块热力图  │   │
                          │  │  • 自选股表    │   │
                          │  │  • 涨幅榜      │   │
                          │  └───────┬───────┘   │
                          │          │ WebSocket  │
                          └──────────┼───────────┘
                                     │
┌─────────────────────────────────────┼───────────────────────────────┐
│           WSL2 / Backend            │                               │
│                                     ▼                               │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │              FastAPI Server (:8000)                       │      │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │      │
│  │  │ REST API    │  │ WebSocket    │  │ QuoteGateway   │  │      │
│  │  │ /quote/{sym}│  │ /ws/market   │  │ (协程实时流)    │  │      │
│  │  └─────────────┘  └──────┬───────┘  └───────┬────────┘  │      │
│  └──────────────────────────┼──────────────────┼───────────┘      │
│                             │                  │                    │
│                             ▼                  ▼                    │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                   Redis (:6379)                           │      │
│  │  ┌──────────────────────────────────────────────────┐    │      │
│  │  │  Stream: "QUOTE_STREAM"                          │    │      │
│  │  │  • 实时行情消息流                                │    │      │
│  │  │  • 消费者组: ws_push, alert_detect               │    │      │
│  │  └──────────────────────────────────────────────────┘    │      │
│  └──────────────────────────────────────────────────────────┘      │
│                             │                                      │
│                             ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │              TimescaleDB (:5432)                          │      │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐ │      │
│  │  │ stock_daily  │  │ stock_minute │  │ 压缩策略: 30天 │ │      │
│  │  │ (日K超表)    │  │ (分钟K超表)  │  │ 自动分区       │ │      │
│  │  └──────────────┘  └──────────────┘  └────────────────┘ │      │
│  └──────────────────────────────────────────────────────────┘      │
│                             │                                      │
│                             ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │              Data Providers                               │      │
│  │  ┌────────────────┐  ┌────────────────┐                   │      │
│  │  │ Tushare Pro    │  │ AkShare        │                   │      │
│  │  │ (备用/历史)    │  │ (主/实时)      │                   │      │
│  │  └────────────────┘  └────────────────┘                   │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 依赖关系与并行策略

```
T1.1 数据源适配层 ──┬── T1.2 TimescaleDB 设计入库
                    │
                    └── T1.3 实时行情网关 ── T1.4 WebSocket ── T1.5 前端Dashboard
                                                                     │
                                                              T1.6 集成测试
```

| 任务 | 预估工时 | 依赖 |
|------|----------|------|
| T1.1 数据源适配层 | 4h | T0.3 |
| T1.2 K 线表设计与入库 | 4h | T1.1 |
| T1.3 实时行情网关 | 6h | T1.1, T0.2 |
| T1.4 WebSocket 推送 | 5h | T1.3 |
| T1.5 前端 Dashboard | 8h | T1.4, T0.4 |
| T1.6 集成测试 | 4h | T1.5 |
| **阶段合计** | **~31h（并行后约 20h）** | |

---

### 阶段 1 验收清单

| 编号 | 验收项 | 验证方式 |
|------|--------|----------|
| 1.1 | 数据源支持获取历史K线 | 单元测试通过 |
| 1.1 | 数据源支持获取实时行情 | 单元测试通过 |
| 1.2 | stock_daily 超表创建成功 | `SELECT count(*) FROM stock_daily;` ≥ 500万 |
| 1.2 | 压缩策略生效 | `SELECT * FROM timescaledb_information.compression_settings;` |
| 1.3 | Redis Stream 收到实时行情 | `XREAD COUNT 5 STREAMS QUOTE_STREAM 0` |
| 1.3 | REST API 返回最新价 | `curl localhost:8000/api/v1/quote/000001.SZ` |
| 1.4 | WebSocket 推送自选股行情 | 前端连接后 2-3 秒收到推送 |
| 1.4 | 异动检测生效 | 涨幅 > 3% 时推送 alert 消息 |
| 1.5 | Dashboard 3 秒内渲染 | 浏览器 Performance 面板测量 |
| 1.5 | 指数卡片实时更新 | 观察数值变化 |
| 1.5 | 板块热力图显示 | ECharts 矩形树图渲染 |
| 1.5 | 涨幅榜显示 | 表格渲染 |
| 1.6 | 断线重连正常 | 重启后端，前端自动恢复 |
| 1.6 | 空数据容错 | 停牌股票显示"暂停交易" |

---

## 阶段 2：选股引擎与复盘报告

### 概述

本阶段在已有行情数据底座上，构建技术面 + 资金面因子库，实现多因子选股评分系统，并接入 LLM 生成每日复盘报告。目标：能按任意因子组合筛选股票，盘后自动产出有分析深度的 HTML/PDF 日报。

### 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Celery Workers                              │
│  ┌──────────────────────┐  ┌────────────────────────────────────┐  │
│  │  Factor Calculation  │  │  Daily Report Generator             │  │
│  │  • 技术因子计算      │  │  • 数据聚合 → LLM 生成 → HTML 导出 │  │
│  │  • 资金因子计算      │  │  • 定时触发: 每天 18:00            │  │
│  │  • 情绪因子计算      │  └────────────────────────────────────┘  │
│  └──────────┬───────────┘                                          │
└─────────────┼───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TimescaleDB 因子层                                │
│  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│  │  factor_daily    │  │  fund_flow     │  │  sentiment       │   │
│  │  • 技术因子日表   │  │  • 北向资金    │  │  • 涨停强度      │   │
│  │  • 30+ 因子列    │  │  • 主力净流入  │  │  • 板块热度      │   │
│  └──────────────────┘  └────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                                   │
│  ┌──────────────────────┐  ┌────────────────────────────────────┐  │
│  │  /api/v1/screener    │  │  /api/v1/reports                   │  │
│  │  多因子选股 + 评分    │  │  报告列表 / 详情 / 下载            │  │
│  └──────────────────────┘  └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Frontend                                         │
│  ┌──────────────────────┐  ┌────────────────────────────────────┐  │
│  │  StockPicker 页面    │  │  Reports 页面                      │  │
│  │  • 条件构建器        │  │  • 报告日期列表                    │  │
│  │  • 因子卡片          │  │  • 在线查看 HTML                   │  │
│  │  • 评分柱状图/表格   │  │  • 下载 PDF                       │  │
│  │  • K线小图弹窗       │  │                                    │  │
│  └──────────────────────┘  └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

### T2.1 技术因子库

#### 目标

基于 **pandas_ta** 实现 30 个以上技术指标因子（纯 Python，安装简单，WSL2 / Windows 均可用），封装为统一的 `FactorCalculator`，支持批量计算。

> **库选型说明**：原文档同时写"TA-Lib 和 pandas_ta"，二者功能重叠，二选一即可。pandas_ta 易装但纯 Python 较慢；若 5000 只股票日频因子计算成为瓶颈，可切换到 **TA-Lib**（需编译 C 库，WSL2 内 `apt install ta-lib` + `pip install TA-Lib`，Windows 原生稍麻烦）或引入 `polars` / `numba` 向量化提速。开发期先用 pandas_ta 跑通，生产再优化。

#### 因子清单（30+）

| 分类 | 因子 | 说明 |
|------|------|------|
| **均线类** | MA5, MA10, MA20, MA60 | 收盘价移动平均 |
| | MA5_MA20_RATIO | 短期/中期均线比，判断趋势强度 |
| | MA_CROSS | 均线排列方向：多头/空头/交叉 |
| **动量类** | MACD_DIF, MACD_DEA, MACD_HIST | MACD 指标 |
| | MACD_GOLDEN_CROSS | MACD 金叉/死叉标记 |
| | RSI_6, RSI_14 | 相对强弱指标 |
| | KDJ_K, KDJ_D, KDJ_J | 随机指标 |
| | WILLIAMS_R | 威廉指标 |
| | BIAS_5, BIAS_10 | 乖离率 |
| **波动类** | BOLL_UP, BOLL_MID, BOLL_DN | 布林带 |
| | BOLL_WIDTH | 布林带宽（波动率） |
| | ATR_14 | 平均真实波幅 |
| **量能类** | VOLUME_RATIO | 量比 = 当日量 / 5日均量 |
| | VOLUME_MA5 | 5日平均成交量 |
| | TURNOVER_RATE | 换手率 |
| **形态类** | DOJI | 十字星检测 |
| | HAMMER | 锤子线检测 |
| | ENGULFING | 吞噬形态检测 |
| | THREE_WHITE | 三白兵（看多） |
| | THREE_BLACK | 三只乌鸦（看空） |

#### 接口设计

```python
class FactorCalculator:
    """技术因子计算器"""

    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        """计算全部技术因子，返回包含因子列的 DataFrame"""
        ...

    @staticmethod
    def compute_single(df: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算单个指定因子"""
        ...
```

#### 目录结构

```
backend/app/services/factor_lib/
├── __init__.py
├── base.py                # FactorCalculator 基类
├── technical.py            # 技术因子实现
├── money.py                # 资金因子实现
└── sentiment.py            # 情绪因子实现
```

#### 验收标准

```python
calculator = FactorCalculator()
df = await provider.get_daily_kline("000001.SZ", "2025-01-01", "2026-06-01")
result = calculator.compute_all(df)
assert result.shape[1] >= 30  # 至少 30 列因子
assert all(0 <= result['RSI_14'].dropna() <= 100)  # RSI 值域校验
```

---

### T2.2 资金与情绪因子

#### 目标

实现资金面（北向资金、主力资金）和情绪面（涨停强度、板块热度）因子，由定时任务更新。

#### 资金因子

| 因子 | 数据源 | 计算方式 |
|------|--------|----------|
| `NORTH_FLOW_TODAY` | Tushare `moneyflow` | 当日北向资金净流入（亿元） |
| `NORTH_FLOW_5D` | Tushare `moneyflow` | 近 5 日北向累计净流入 |
| `MAIN_NET_INFLOW` | AkShare `stock_individual_fund_flow` | 主力（超大单+大单）净流入占比 |
| `MAIN_NET_INFLOW_5D` | AkShare | 近 5 日主力净流入累计 |
| `RETAIL_NET_INFLOW` | AkShare | 散户净流入占比 |

#### 情绪因子

| 因子 | 数据源 | 计算方式 |
|------|--------|----------|
| `LIMIT_UP_COUNT` | AkShare `stock_zt_pool` | 当日涨停家数 |
| `LIMIT_DOWN_COUNT` | AkShare `stock_zt_pool` | 当日跌停家数 |
| `LIMIT_UP_RATIO` | — | 涨停数量 / 全市场股票数 |
| `SECTOR_HOT_SCORE` | Tushare `concept` | 板块内涨停股占比 |
| `ZDT_COUNT` | — | 炸板率 (开板数/涨停触及数) |

#### 因子表结构（DDL，原文档缺失，阶段 2 落地必备）

选股器（T2.3）与回测（T4.4）都引用 `factor_daily`，但原文档未给建表语句，此处补齐。
`trade_date` 用 `DATE`（非 `TIMESTAMPTZ`）以彻底避免时区导致的 ±1 天偏移，全库统一按 `Asia/Shanghai` 口径处理。

```sql
-- 技术 / 资金 / 情绪因子日表：每股票每日一行
CREATE TABLE factor_daily (
    symbol              TEXT        NOT NULL,
    trade_date          DATE        NOT NULL,
    -- 均线类
    ma5                 NUMERIC(10,2),
    ma10                NUMERIC(10,2),
    ma20                NUMERIC(10,2),
    ma60                NUMERIC(10,2),
    ma5_ma20_ratio      NUMERIC(8,4),
    ma_cross            SMALLINT,       -- 1=多头排列 0=交叉 -1=空头排列
    -- 动量类
    macd_dif            NUMERIC(10,4),
    macd_dea            NUMERIC(10,4),
    macd_hist           NUMERIC(10,4),
    macd_golden_cross   BOOLEAN,
    rsi_6               NUMERIC(6,2),
    rsi_14              NUMERIC(6,2),
    kdj_k               NUMERIC(8,2),
    kdj_d               NUMERIC(8,2),
    kdj_j               NUMERIC(8,2),
    williams_r          NUMERIC(8,2),
    bias_5              NUMERIC(8,4),
    bias_10             NUMERIC(8,4),
    -- 波动类
    boll_up             NUMERIC(10,2),
    boll_mid            NUMERIC(10,2),
    boll_dn             NUMERIC(10,2),
    boll_width          NUMERIC(8,4),
    atr_14              NUMERIC(10,2),
    -- 量能类
    volume_ratio        NUMERIC(8,4),
    volume_ma5          BIGINT,
    turnover_rate       NUMERIC(6,4),
    -- 形态类（布尔）
    doji                BOOLEAN,
    hammer              BOOLEAN,
    engulfing           BOOLEAN,
    three_white         BOOLEAN,
    three_black         BOOLEAN,
    -- 资金面
    north_flow_today    NUMERIC(12,2),  -- 北向当日净流入（亿元）
    north_flow_5d       NUMERIC(12,2),
    main_net_inflow     NUMERIC(12,2),  -- 主力净流入（亿元）
    main_net_inflow_5d  NUMERIC(12,2),
    retail_net_inflow   NUMERIC(12,2),
    -- 情绪面
    limit_up_count      INTEGER,
    limit_down_count    INTEGER,
    limit_up_ratio      NUMERIC(8,4),
    sector_hot_score    NUMERIC(8,4),
    zdt_count           NUMERIC(8,4),
    -- 舆情因子（阶段 3 填充，见 T3.3）
    positive_news_1d    INTEGER,
    negative_news_1d    INTEGER,
    sentiment_score_1d  NUMERIC(5,4),
    positive_news_3d    INTEGER,
    sentiment_trend     NUMERIC(6,4),
    PRIMARY KEY (symbol, trade_date)
);
CREATE INDEX idx_factor_date ON factor_daily (trade_date DESC);

-- 资金流明细（盘后落库，可选）
CREATE TABLE fund_flow (
    symbol      TEXT    NOT NULL,
    trade_date  DATE    NOT NULL,
    north_in    NUMERIC(12,2),
    north_out   NUMERIC(12,2),
    main_in     NUMERIC(12,2),
    main_out    NUMERIC(12,2),
    retail_in   NUMERIC(12,2),
    retail_out  NUMERIC(12,2),
    PRIMARY KEY (symbol, trade_date)
);

-- 板块热度（情绪因子来源）
CREATE TABLE sector_sentiment (
    sector      TEXT    NOT NULL,
    trade_date  DATE    NOT NULL,
    limit_up_num INTEGER,
    total_num    INTEGER,
    hot_score    NUMERIC(8,4),
    PRIMARY KEY (sector, trade_date)
);
```

> `FactorCalculator.compute_all()` 返回的 DataFrame 列名需与上面字段一一对应；选股器（T2.3）通过 DuckDB / PG 查询此表。

#### 定时任务

```python
# backend/app/tasks/data_collect.py

@celery.task  # 每天 15:30 执行
def sync_fund_flow():
    """盘后同步资金流向数据"""
    ...

@celery.task  # 每天 15:45 执行
def sync_sentiment():
    """盘后同步情绪数据"""
    ...

@celery.task  # 每天 16:00 执行
def compute_all_factors():
    """计算并入库全部因子"""
    ...
```

#### 验收标准

- 交易日 15:30 后，`factor_daily` 表中有当日因子数据
- `NORTH_FLOW_TODAY` 值在合理范围内（-200 ~ +200 亿元）

---

### T2.3 选股器后台（多因子评分）

#### 目标

实现 `/api/v1/screener` 接口，支持条件组合查询，加权评分返回 Top N。

#### API 设计

```json
POST /api/v1/screener
{
  "conditions": [
    {"factor": "MA_CROSS", "op": "eq", "value": "多头排列"},
    {"factor": "MACD_GOLDEN_CROSS", "op": "eq", "value": true},
    {"factor": "NORTH_FLOW_5D", "op": "gt", "value": 10},
    {"factor": "RSI_14", "op": "between", "value": [30, 70]}
  ],
  "logic": "AND",
  "weights": {
    "MA_CROSS": 0.3,
    "MACD_GOLDEN_CROSS": 0.2,
    "NORTH_FLOW_5D": 0.3,
    "RSI_14": 0.2
  },
  "top_n": 20,
  "date": "2026-06-04"
}
```

**响应**

```json
{
  "total": 45,
  "stocks": [
    {
      "symbol": "000001.SZ",
      "name": "平安银行",
      "score": 85.3,
      "factors": {
        "MA_CROSS": "多头排列",
        "MACD_GOLDEN_CROSS": true,
        "NORTH_FLOW_5D": 12.5,
        "RSI_14": 55.2
      },
      "reason": "均线多头排列，MACD金叉，北向资金近5日持续流入"
    }
  ]
}
```

#### 核心模块

```
backend/app/services/stock_picker.py     # 选股评分主逻辑
backend/app/tasks/screening.py           # Celery 异步筛选任务
```

#### 评分引擎设计

```
1. 条件解析 → 转化为 SQL WHERE 子句 + 权重向量
2. 因子值查询 → 从 factor_daily 表查询符合条件股票
3. 评分计算 → score = Σ(权重 × 归一化因子值) × 100
4. 原因生成 → 根据命中的因子组合拼接自然语言描述
5. 返回 Top N
```

> **因子归一化方案（必须定义，否则分类/布尔/数值无法混算）**：
> - 分类因子（如 `ma_cross`）：映射为序数，`多头排列=1 / 交叉=0.5 / 空头排列=0`；
> - 布尔因子（如 `macd_golden_cross`）：`True=1 / False=0`；
> - 数值因子（如 `rsi_14`、`north_flow_5d`）：先 min-max 归一化到 `[0,1]`（方向因子取负向），或用截面 z-score；
> - 舆情因子（`sentiment_score_1d` 已归一化到 `[0,1]`）直接入算。
> - **权重归一**：所有因子权重之和必须 = 1（`Σw = 1`），再加权求和 × 100 得到 0~100 分。
> - 归一化的参考基准建议用**当日全市场截面**（而非个股历史），保证选股在同一交易日可比。

#### 查询引擎：DuckDB 加速（非纯净系统友好）

选股筛选中涉及大量因子表的多维分析查询，在 TimescaleDB 上可能较慢。引入 DuckDB 作为分析查询引擎：

```diff
- 所有查询走 TimescaleDB（行存，OLTP 场景最优）
+ 写入/实时查询 → TimescaleDB
+ 分析查询/选股/回测 → DuckDB（列存，OLAP 场景快 10-50 倍）
```

DuckDB 的优势：

- 嵌入在 Python 进程中，**零额外服务开销**
- 内存按需分配，**用完释放**，不抢资源
- 通过 `postgres_scanner` 扩展**直接查询 TimescaleDB**，无需数据搬运或 ETL
- 非纯净系统下比单独起一个 PG 分析实例省得多

```python
# DuckDB 直接扫描 TimescaleDB 示例
import duckdb

duckdb.sql("""
    INSTALL postgres_scanner;
    LOAD postgres_scanner;

    SELECT symbol, trade_date, close, ma_cross, rsi_14
    FROM postgres_scan('host=localhost port=5432 dbname=trading user=postgres password=xxx',
                       'public', 'factor_daily')
    WHERE trade_date = '2026-06-04'
    AND ma_cross = '多头排列'
    AND rsi_14 BETWEEN 30 AND 70
""")
```

> 注意：`postgres_scanner` 将查询下推到 PG 执行，DuckDB 仅做结果缓存和向量化加速。对于扫全表的聚集查询，可在 DuckDB 中 `CREATE TABLE factor_cache AS SELECT * FROM postgres_scan(...)` 将数据拉到 DuckDB 内存列存，后续分析不再访问 PG。

```python
# backend/app/core/query_router.py
class QueryRouter:
    """查询路由：实时查询 → TimescaleDB，分析查询 → DuckDB"""

    @staticmethod
    async def screener_query(conditions, weights, top_n):
        """选股查询路由到 DuckDB"""
        # 1. 从 TimescaleDB 拉取当日因子数据（仅需要的列）
        # 2. 加载到 DuckDB 内存（按需）
        # 3. 执行多维过滤 + 评分计算
        # 4. 返回 Top N
        ...

    @staticmethod
    async def realtime_quote(symbol):
        """实时行情走 TimescaleDB"""
        ...
```

#### 验收标准

```bash
curl -X POST http://localhost:8000/api/v1/screener \
  -H "Content-Type: application/json" \
  -d '{"conditions":[{"factor":"MA_CROSS","op":"eq","value":"多头排列"}],"top_n":10}'
# 响应时间 < 2s，返回股票列表含评分和原因
```

---

### T2.4 选股器 UI（前端）

#### 目标

实现条件构建器界面，支持 And/Or 逻辑组，可视化因子选择和评分展示。

#### 页面布局

```
┌──────────────────────────────────────────────────────────────────┐
│  选股器                                                          │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐     │
│  │  条件构建区域                                            │     │
│  │  ┌────────────────────────────────────────────────┐    │     │
│  │  │  AND 组                                         │    │     │
│  │  │  ├── [均线排列] [等于] [多头排列]    [×]        │    │     │
│  │  │  ├── [MACD金叉] [等于] [true]       [×]        │    │     │
│  │  │  ├── [北向5日] [大于] [10]          [×]        │    │     │
│  │  │  └── [+ 添加条件]                              │    │     │
│  │  │                                                   │    │     │
│  │  │  OR 组                                          │    │     │
│  │  │  ├── [RSI_14] [介于] [30, 70]        [×]        │    │     │
│  │  │  └── [+ 添加条件]                              │    │     │
│  │  │                                                   │    │     │
│  │  │  [+ 添加 AND 组] [+ 添加 OR 组]                 │    │     │
│  │  └────────────────────────────────────────────────┘    │     │
│  │  [权重配置] [筛选]  [对比模式 ☐]                       │     │
│  └────────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐     │
│  │  结果区域（Top 20）                                     │     │
│  │  ┌──────┬────────┬────────┬────────┬────────┬──────┐  │     │
│  │  │ 代码  │ 名称   │ 评分   │ 均线   │ MACD  │ 详情 │  │     │
│  │  │000001│平安银行│ 85.3  │ 多头   │ 金叉  │ [K线]│  │     │
│  │  │600519│贵州茅台│ 78.1  │ 多头   │ 金叉  │ [K线]│  │     │
│  │  └──────┴────────┴────────┴────────┴────────┴──────┘  │     │
│  │  ┌─────────────────────────────────────────────────┐   │     │
│  │  │  评分分布柱状图（ECharts）                       │   │     │
│  │  └─────────────────────────────────────────────────┘   │     │
│  └────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

#### 文件清单

```
frontend/src/pages/StockPicker/
├── index.tsx                    # 页面入口
├── components/
│   ├── ConditionBuilder.tsx     # 条件构建器（And/Or 组）
│   ├── FactorCard.tsx           # 单条条件卡片
│   ├── WeightConfig.tsx         # 权重配置面板
│   ├── ResultTable.tsx          # 评分结果表格
│   └── ScoreChart.tsx           # 评分柱状图
├── hooks/
│   └── useStockPicker.ts        # 选股逻辑 Hook
└── types.ts                     # 类型定义
```

#### 验收标准

- 选择"均线多头 + 北向流入"条件后，点击筛选，2 秒内展示股票列表
- 点击股票行"K线"按钮，弹出 K 线小图
- 评分柱状图按分数从高到低排列
- 勾选多只股票进入对比模式，显示多股 K 线叠加 + 因子雷达图

---

### T2.5 每日复盘报告生成（AI 增强版）

#### 目标

盘后定时汇总数据，构造结构化 Prompt，调用 Ollama Qwen2.5-14B 生成自然语言复盘文本，导出为 HTML/PDF。

#### 报告内容结构

```
┌─────────────────────────────────────┐
│  A股复盘日报 — 2026-06-04          │
├─────────────────────────────────────┤
│  一、大盘回顾                       │
│  ├── 指数表现（上证/深证/创业板）   │
│  ├── 涨跌家数统计                   │
│  └── 成交量变化                     │
│                                     │
│  二、板块资金热度                   │
│  ├── 领涨板块 Top 5                │
│  ├── 领跌板块 Top 5                │
│  └── 板块资金净流入 Top 5          │
│                                     │
│  三、资金面分析                     │
│  ├── 北向资金净流入/流出            │
│  ├── 主力资金流向                   │
│  └── 融资融券变化                   │
│                                     │
│  四、涨停板复盘                     │
│  ├── 涨停数量 / 跌停数量            │
│  ├── 连板梯队（最高板/3板以上）     │
│  └── 板块分布                       │
│                                     │
│  五、AI 市场解读                    │
│  ├── 大势研判                       │
│  ├── 主线板块识别                   │
│  ├── 风险提示                       │
│  └── 次日关注方向                   │
└─────────────────────────────────────┘
```

#### LLM Prompt 设计

```python
# backend/app/tasks/daily_report.py

REPORT_PROMPT = """你是一位专业的A股市场分析师。请根据以下结构化数据，撰写一份专业的复盘日报。

【大盘数据】
- 上证指数: {sh_index} 涨跌幅: {sh_pct}%
- 深证成指: {sz_index} 涨跌幅: {sz_pct}%
- 创业板指: {cy_index} 涨跌幅: {cy_pct}%
- 上涨家数: {up_count} 下跌家数: {down_count}

【板块数据】
- 领涨板块: {top_sectors}
- 领跌板块: {bottom_sectors}

【资金数据】
- 北向资金: {north_flow}亿元
- 主力资金: {main_flow}亿元

【涨停数据】
- 涨停: {limit_up}只 跌停: {limit_down}只
- 连板股: {consecutive_stocks}

请从以下五个方面进行分析：
1. 大势研判：今日市场整体走势和特征
2. 主线板块：当前市场主线板块及持续性分析
3. 资金态度：北向和主力资金透露的信号
4. 风险提示：需警惕的风险因素
5. 次日关注：明日值得跟踪的方向和逻辑

要求：语言专业、数据驱动、观点明确。全文约800-1200字。"""
```

#### 报告生成流程

```
1. Celery 定时任务触发（每天 18:00）
2. 从 TimescaleDB 汇总当日数据（指数、板块、资金、涨停）
3. 构造结构化数据字典
4. 调用 LLMService.generate() 传入 Prompt + 结构化数据
5. 解析 LLM 返回文本
6. 渲染 HTML 模板（Jinja2）
7. 生成 PDF（**推荐 Playwright headless Chromium 打印 HTML→PDF**，中文与样式支持最好；若用 WeasyPrint 需先装 pango/cairo 等系统库，WSL2 易踩坑；wkhtmltopdf 已停止维护，不推荐）
8. 保存：HTML 正文与元数据存入 `reports` 表（数据库），PDF 文件按需由 HTML 临时渲染导出，不必常驻磁盘双写——避免库与文件不一致
9. WebSocket 推送通知前端有新报告
```

#### 文件清单

```
backend/app/tasks/daily_report.py      # 报告生成 Celery 任务
backend/app/templates/report.html      # HTML 模板（Jinja2）
backend/app/services/report_service.py # 报告数据聚合 + LLM 调用
scripts/generate_report.py             # 手动触发脚本（用于调试）
```

#### 验收标准

- 每天 18:00 自动触发，15 分钟内生成完成（含 LLM 推理时间）
- 报告内容连贯、专业，数据与当日行情一致
- LLM AI 分析部分有理有据，不少于 800 字

---

### T2.6 报告前端展示

#### 目标

报告列表页面，支持按日期浏览、在线查看 HTML 报告、下载 PDF。

#### 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│  每日复盘报告                                                  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────┬──────────┬──────────┬──────────┬────────────────┐ │
│  │ 日期 │ 大盘涨跌 │ 涨停数   │ 北向资金 │ 操作           │ │
│  ├─────┼──────────┼──────────┼──────────┼────────────────┤ │
│  │06-04│ 上证+0.85│ 72       │+45.2亿  │ [阅读] [下载]  │ │
│  │06-03│ 上证-0.32│ 38       │-12.5亿  │ [阅读] [下载]  │ │
│  │05-31│ 上证+1.15│ 85       │+68.3亿  │ [阅读] [下载]  │ │
│  └─────┴──────────┴──────────┴──────────┴────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  [点击阅读 → 内嵌 HTML 报告查看器]                           │
└─────────────────────────────────────────────────────────────┘
```

#### 文件清单

```
frontend/src/pages/Reports/
├── index.tsx                    # 报告列表页
├── components/
│   ├── ReportList.tsx           # 报告日期列表
│   └── ReportViewer.tsx         # HTML 报告查看器（iframe）
└── hooks/
    └── useReports.ts            # 报告列表数据 Hook
```

#### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/reports` | 报告列表（分页） |
| GET | `/api/v1/reports/{date}` | 报告详情（含 HTML 内容） |
| GET | `/api/v1/reports/{date}/pdf` | 下载 PDF |
| GET | `/api/v1/reports/{date}/email` | 发送报告到预设邮箱 |

#### 邮件推送

报告生成后，可选自动发送到指定邮箱：

```python
# backend/app/tasks/daily_report.py — 新增步骤
def send_report_email(report_date: str):
    """将当日报告作为 HTML 正文发送到预设邮箱"""
    ...  # 使用 smtplib + 邮件 SMTP 配置

# 配置项（.env）
REPORT_EMAIL_ENABLED=true
REPORT_EMAIL_TO=user@example.com
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=xxx@qq.com
SMTP_PASSWORD=xxx
```

#### 验收标准

- 报告列表按日期倒序排列，每日生成一条
- 点击"阅读"后，页面内展示报告 HTML
- 点击"下载"下载 PDF 文件

---

### 阶段 2 整体数据流

```
                         ┌──────────────────────┐
                         │   Ollama Qwen2.5-14B  │
                         │   LLM 分析生成        │
                         └──────┬───────────────┘
                                │
  ┌─────────────────────────────┼─────────────────────────────┐
  │  Celery Workers             │                              │
  │                             ▼                              │
  │  ┌───────────────────────────────────────────────────┐   │
  │  │  Daily Report Generator                            │   │
  │  │  ① 汇总数据 ② 调用 LLM ③ 渲染 HTML ④ 生成 PDF   │   │
  │  └───────────────────────────────────────────────────┘   │
  │                                                          │
  │  ┌───────────────────────────────────────────────────┐   │
  │  │  Factor Computation Pipeline                      │   │
  │  │  Tushare/AkShare → 因子计算 → factor_daily 表    │   │
  │  │                               ↓                   │   │
  │  │                    Stock Screener (选股评分)      │   │
  │  └───────────────────────────────────────────────────┘   │
  └──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                        │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │ /api/v1/screener│  │/api/v1/reports │  │ /api/v1/factors│ │
│  │ 选股评分接口    │  │ 报告CRUD       │  │ 因子查询接口   │ │
│  └────────────────┘  └────────────────┘  └────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                               │
│  ┌────────────────────────┐  ┌────────────────────────────┐  │
│  │  StockPicker 选股器    │  │  Reports 复盘报告          │  │
│  │  → 条件构建 → 评分结果   │  │  → 列表 → 阅读/下载      │  │
│  └────────────────────────┘  └────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

### 依赖关系与并行策略

```
T2.1 技术因子库 ──┬── T2.3 选股器后台 ── T2.4 选股器 UI
                   │
T2.2 资金情绪因子 ──┘
                   │
                   └── T2.5 复盘报告 ── T2.6 报告前端
```

| 任务 | 预估工时 | 依赖 |
|------|----------|------|
| T2.1 技术因子库 | 6h | T1.2 |
| T2.2 资金情绪因子 | 6h | T1.1, T1.2 |
| T2.3 选股器后台 | 8h | T2.1, T2.2 |
| T2.4 选股器 UI | 8h | T2.3 |
| T2.5 复盘报告生成 | 10h | T2.2, T0.5 |
| T2.6 报告前端展示 | 4h | T2.5 |
| **阶段合计** | **~42h（并行后约 28h）** | |

> 注意：T2.1 和 T2.2 可完全并行。T2.5 无需等待 T2.3/T2.4，可与选股器并行开发。
>
> **版本**：T2.4 对比模式归入 V1.1，其余均为 V1.0。

---

### 阶段 2 验收清单

| 编号 | 验收项 | 验证方式 |
|------|--------|----------|
| 2.1 | 30+ 技术因子计算 | `compute_all()` 返回 30+ 列因子 DataFrame |
| 2.1 | 因子值域合理 | RSI ∈ [0,100]，MA5/MA10/MA20 均为正值 |
| 2.2 | 资金因子入库 | 15:30 后 `factor_daily` 表有当日数据 |
| 2.2 | 北向资金值域 | -200 ≤ NORTH_FLOW_TODAY ≤ 200 |
| 2.3 | 选股 API 响应 < 2s | `time curl POST /api/v1/screener` 实测 |
| 2.3 | 评分结果有原因描述 | `reason` 字段非空 |
| 2.4 | 条件构建器可用 | 组合 3 个以上条件筛选出结果 |
| 2.4 | K 线小图弹窗 | 点击"K线"按钮弹出窗口展示图表 |
| 2.5 | 每日 18:00 自动生成报告 | 查看报告列表有当日记录 |
| 2.5 | AI 分析专业连贯 | 人工评审报告内容质量 |
| 2.5 | 报告结构完整 | 5 个章节齐全（大势/板块/资金/涨停/AI解读） |
| 2.5 | HTML 模板渲染正常 | 浏览器打开报告 HTML 样式正确 |
| 2.5 | PDF 导出正常 | 下载的 PDF 可正常打开 |
| 2.6 | 报告列表按日期排序 | 列表倒序排列 |
| 2.6 | 阅读/下载功能正常 | 点击后显示报告 / 下载文件 |

---

## 阶段 3：舆情与情绪引擎

### 概述

本阶段构建自动化舆情处理管线，从财经新闻源实时抓取，经 FinBERT 中文情感模型推理，产出舆情因子融入选股评分，并在前端以情绪标记形式可视化展示。目标：让选股器能感知市场情绪温度，K 线图上可看到重大新闻事件标记。

### 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                   Celery Workers (定时 + 链式)                    │
│                                                                  │
│  T3.1 抓取 ──→ T3.2 推理 ──→ T3.3 因子入库                        │
│                                                                  │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────────┐   │
│  │ News         │───▶│  FinBERT-zh     │───▶│  Emotion      │   │
│  │ Crawler      │    │  GPU 批量推理    │    │  Factor Merge │   │
│  │ (每 10min)   │    │  (4K/批次)       │    │               │   │
│  └──────┬───────┘    └─────────────────┘    └───────┬───────┘   │
└─────────┼────────────────────────────────────────────┼───────────┘
          │                                             │
          ▼                                             ▼
┌──────────────────┐                       ┌──────────────────────┐
│  TimescaleDB     │                       │  TimescaleDB         │
│  (即 PostgreSQL+  │                       │  factor_daily        │
│   扩展，同一实例) │                       │  + sentiment 因子列   │
│  news_raw        │                       │                       │
│  • 标题/正文     │                       └──────────────────────┘
│  • 来源/时间     │
│  • 相关股票      │
│  • 情感标签      │
└──────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│                         FastAPI Backend                           │
│  ┌────────────────────┐  ┌───────────────────────────────────┐  │
│  │ /api/v1/news       │  │ /api/v1/screener (增强)           │  │
│  │ 新闻流 / 筛选       │  │ 增加舆情因子权重                  │  │
│  └────────────────────┘  └───────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│  ┌────────────────────┐  ┌───────────────────────────────────┐  │
│  │ News 新闻流页面    │  │ KLineChart + 新闻事件标记         │  │
│  │ 实时滚动 / 情感筛  │  │ 重大新闻 Markers                  │  │
│  └────────────────────┘  └───────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

### T3.1 新闻抓取服务

#### 目标

定时抓取财联社电报、雪球热帖、东方财富新闻，写入 `news_raw` 表，自动去重。

#### 数据源

| 来源 | 内容类型 | 抓取频率 | 实现方式 |
|------|----------|----------|----------|
| **财联社电报** | 快讯/盘中消息 | 每 10 分钟 | AkShare `stock_info_news` / HTTP API |
| **雪球热帖** | 讨论/分析 | 每 30 分钟 | AkShare / RSS |
| **东方财富新闻** | 资讯/公告 | 每 15 分钟 | AkShare `stock_info_news` |

#### 表结构

```sql
CREATE TABLE news_raw (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT        NOT NULL,         -- 来源: cls / xueqiu / eastmoney
    title         TEXT        NOT NULL,
    content       TEXT,
    url           TEXT        UNIQUE,
    publish_time  TIMESTAMPTZ NOT NULL,
    crawl_time    TIMESTAMPTZ DEFAULT NOW(),
    related_stocks TEXT[],                       -- 相关股票代码数组
    sentiment_label  TEXT,                       -- positive / negative / neutral
    sentiment_score NUMERIC(5,4),                -- 情感强度 0.0 ~ 1.0
    is_duplicate  BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_news_publish_time ON news_raw (publish_time DESC);
CREATE INDEX idx_news_stock ON news_raw USING GIN (related_stocks);
CREATE INDEX idx_news_sentiment ON news_raw (sentiment_label);
```

#### 目录结构

```
backend/app/services/news_crawler/
├── __init__.py
├── base.py                    # BaseCrawler 基类
├── cls_crawler.py             # 财联社抓取（每 10 分钟）
├── xueqiu_crawler.py          # 雪球抓取（每 30 分钟）
├── eastmoney_crawler.py       # 东方财富抓取（每 15 分钟）
├── cnbc_crawler.py            # CNBC / Reuters 境外新闻（每 60 分钟，盘后集中抓取）
├── seekingalpha_crawler.py    # Seeking Alpha 美股分析
├── translator.py              # 翻译层（调用 Qwen2.5-3B 零样本翻译）
├── dedup.py                   # 去重逻辑（URL + 标题相似度）
└── models.py                  # SQLAlchemy 模型
```

#### Celery Beat 配置

```python
# backend/app/core/celery_app.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    "crawl-cls-every-10min": {
        "task": "app.tasks.news_tasks.crawl_cls",
        "schedule": crontab(minute="*/10"),
    },
    "crawl-eastmoney-every-15min": {
        "task": "app.tasks.news_tasks.crawl_eastmoney",
        "schedule": crontab(minute="*/15"),
    },
    "crawl-xueqiu-every-30min": {
        "task": "app.tasks.news_tasks.crawl_xueqiu",
        "schedule": crontab(minute="*/30"),
    },
    # 境外新闻仅在盘后集中抓取，避免盘中占用网络/CPU
    "crawl-overseas-at-17": {
        "task": "app.tasks.news_tasks.crawl_overseas",
        "schedule": crontab(hour=17, minute=0),  # 每天 17:00
    },
    "crawl-overseas-at-8": {
        "task": "app.tasks.news_tasks.crawl_overseas",
        "schedule": crontab(hour=8, minute=0),   # 开盘前 08:00
    },
}
```

#### 数据源配置表

| 来源 | 区域 | 抓取频率 | 备注 |
|------|------|----------|------|
| 财联社电报 | 国内 | 每 10 分钟 | 盘中快讯 |
| 东方财富新闻 | 国内 | 每 15 分钟 | 资讯/公告 |
| 雪球热帖 | 国内 | 每 30 分钟 | 讨论/分析 |
| CNBC / Reuters | 境外 | 每天 08:00 + 17:00 | 隔夜美股/全球热点 |
| Seeking Alpha | 境外 | 每天 08:00 + 17:00 | 美股分析/行业趋势 |
| Google Trends | 境外 | 每天 08:00 | AI 板块全球热度（可选） |

#### 验收标准

```sql
SELECT count(*) FROM news_raw WHERE crawl_time > NOW() - INTERVAL '1 hour';
-- 预期 >= 200 条

-- 去重验证
SELECT count(*) FROM news_raw WHERE is_duplicate = FALSE;
-- 去重正常
```

---

### T3.2 FinBERT 模型部署与批量推理

#### 目标

部署 FinBERT-zh（中文金融情感模型），实现 GPU 加速批量推理，抓取后自动对新闻文本进行情感三分类。

#### 模型选型

| 模型 | 参数 | 用途 | 来源 |
|------|------|------|------|
| **FinBERT-zh** | 110M | 中文金融文本情感三分类（正面/负面/中性） | 选用**金融领域三分类**中文模型，例如 `shibing624/finbert-base-chinese` 或 `csebuetnlp/finbert`（英文需先翻译）的金融中文微调版；**不要用** `uer/roberta-base-finetuned-jd-binary-chinese`（那是京东评论二分类模型，粒度与标签数都不对） |

> 也可使用 `ProsusAI/finbert` + 中文翻译管道，但推荐直接使用中文金融预训练模型以获得更好的准确率。

#### 推理服务设计

```python
class FinBERTService:
    """FinBERT 情感推理服务"""

    def __init__(self, model_name: str = "path/to/finbert-zh"):
        """加载模型到 GPU（RTX 5080）"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

    def predict_batch(self, texts: list[str], batch_size: int = 64) -> list[dict]:
        """批量推理，返回情感标签及置信度"""
        ...

    def predict_single(self, text: str) -> dict:
        """单条推理"""
        ...
```

#### 定时任务链

```
抓取完成 ──→ Celery chain ──→ FinBERT 批量推理 ──→ 更新 news_raw.sentiment_*
```

```python
# backend/app/tasks/news_analysis.py
from celery import chain

@celery.task
def analyze_news_batch():
    """批量分析未处理新闻的情感"""
    # 1. 查询 sentiment_label IS NULL 的新闻
    # 2. 按批次 (batch_size=64) 调用 FinBERT
    # 3. 批量更新 news_raw
    ...

# 链式配置：抓取完成后自动触发推理
crawl_and_analyze = chain(
    crawl_cls.s(),
    analyze_news_batch.s()
)
```

#### GPU 资源规划

| 模型 | VRAM 占用 | RTX 5080 (16GB) 余量 |
|------|-----------|---------------------|
| FinBERT-zh (110M) | ~1.5GB | 22.5GB 空闲 |
| 与 Qwen 共存策略 | FinBERT 推理速度极快（<1s/100条），可与 Ollama 共享 GPU |

#### 验收标准

```bash
# 100 条新闻批量推理耗时
curl http://localhost:8000/api/v1/news/analyze-test
# 100 条 in 30s → PASS

# 情感分类合理性
# 输入: "公司发布重大资产重组方案，利好"
# 输出: {label: "positive", score: 0.967}
```

---

### T3.3 舆情因子接入选股器

#### 目标

将情感分析结果整合为可用因子，融入选股评分引擎。

#### 舆情因子

| 因子名 | 计算方式 | 权重建议 |
|--------|----------|----------|
| `POSITIVE_NEWS_1D` | 当日正面新闻数 | 0.1 |
| `NEGATIVE_NEWS_1D` | 当日负面新闻数 | -0.15 |
| `SENTIMENT_SCORE_1D` | Σ(正面强度) - Σ(负面强度)，归一化到 [0,1] | 0.15 |
| `POSITIVE_NEWS_3D` | 近 3 日正面新闻滚动合计 | 0.1 |
| `SENTIMENT_TREND` | 近 3 日情感趋势（连续改善 → 加分） | 0.05 |

#### 修改点

```
backend/app/services/stock_picker.py
  ├── 新增：_apply_sentiment_factors()  # 从 news_raw 聚合情感因子
  ├── 修改：_build_scoring_weights()     # 加入舆情权重默认值
  └── 修改：get_screening_reason()       # 舆情因子加入原因描述
```

#### 选股示例

```json
POST /api/v1/screener
{
  "conditions": [
    {"factor": "MA_CROSS", "op": "eq", "value": "多头排列"},
    {"factor": "POSITIVE_NEWS_1D", "op": "gt", "value": 3}
  ],
  "weights": {
    "MA_CROSS": 0.4,
    "POSITIVE_NEWS_1D": 0.3,
    "SENTIMENT_SCORE_1D": 0.3
  },
  "top_n": 20
}
```

#### 验收标准

```bash
curl -X POST http://localhost:8000/api/v1/screener \
  -H "Content-Type: application/json" \
  -d '{"conditions":[{"factor":"POSITIVE_NEWS_1D","op":"gt","value":3}],"top_n":10}'
# 结果应包含近期有重大利好消息的股票
```

---

### T3.4 新闻列表前端

#### 目标

展示实时新闻流，支持按来源/股票/情感筛选，个股 K 线图上叠加重大新闻标记。

#### 新闻流页面布局

```
┌──────────────────────────────────────────────────────────────────┐
│  舆情                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────┐  ┌────────────────────────┐ │
│  │  实时新闻流                      │  │  筛选面板              │ │
│  │                                 │  │  ┌──────────────────┐ │ │
│  │  🔴 [财联社] 09:32              │  │  │ 来源: □全部      │ │
│  │  半导体板块持续走强，韦尔股份... │  │  │       □财联社    │ │
│  │  ──────────────────────────    │  │  │       □雪球      │ │
│  │  🟢 [东财] 09:28               │  │  │       □东财      │ │
│  │  市场担忧流动性收紧，三大指数...│  │  ├──────────────────┤ │
│  │  ──────────────────────────    │  │  │ 情绪: □全部      │ │
│  │  🔴 [雪球] 09:15               │  │  │       □正面 🔴   │ │
│  │  某知名分析师看好 AI 算力赛道  │  │  │       □负面 🟢   │ │
│  │  ──────────────────────────    │  │  │       □中性 ⚪   │ │
│  │  🟢 [财联社] 09:10             │  │  ├──────────────────┤ │ │
│  │  地产板块利空，融创股价大跌...  │  │  │ 标的筛选:        │ │ │
│  │  ──────────────────────────    │  │  │ [输入股票代码]   │ │ │
│  │  ... 实时滚动 ...              │  │  └──────────────────┘ │ │
│  └─────────────────────────────────┘  └────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│  个股详情 → K 线 + 事件标记                                       │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │  贵州茅台 600519  日K                                         ││
│  │  ┌──────────────────────────────────────────────────────┐   ││
│  │  │                                                      │   ││
│  │  │          ⚠️ 利好公告                                   │   ││
│  │  │     📈  ████████                                      │   ││
│  │  │     ████████████                                      │   ││
│  │  │  ⚠️ 减持 ████████████████                             │   ││
│  │  │     ██████████████████████                            │   ││
│  │  │                        ⚠️ 业绩预告                     │   ││
│  │  └──────────────────────────────────────────────────────┘   ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

#### 文件清单

```
frontend/src/pages/News/
├── index.tsx                    # 新闻流页面
├── components/
│   ├── NewsStream.tsx           # 实时新闻流（虚拟滚动）
│   ├── NewsCard.tsx             # 单条新闻卡片（含情感色标）
│   ├── NewsFilter.tsx           # 筛选面板
│   └── StockNewsSidebar.tsx     # 个股相关新闻侧栏
└── hooks/
    └── useNewsStream.ts         # WebSocket 新闻流 Hook

# K 线事件标记（修改已有组件）
frontend/src/components/KLineChart/
├── index.tsx                    # 增加 eventMarkers prop
└── types.ts                     # 增加 EventMarker 类型
```

#### WebSocket 新闻推送

在已有的 `/ws/market` 中增加新闻消息类型：

```json
{
  "type": "news",
  "data": {
    "id": 12345,
    "source": "cls",
    "title": "半导体板块持续走强",
    "sentiment_label": "positive",
    "publish_time": "2026-06-04T09:32:00Z"
  }
}
```

#### 情感色标

| 情感 | 色标 | 用途 |
|------|------|------|
| `positive` | 🔴 红色 `#f5222d` | 正面/利好新闻（与 A 股"红涨"一致） |
| `negative` | 🟢 绿色 `#52c41a` | 负面/利空新闻（与 A 股"绿跌"一致） |
| `neutral` | ⚪ 灰色 `#d9d9d9` | 中性新闻 |

> ⚠️ **配色统一**：A 股惯例是"涨/利好=红、跌/利空=绿"，与西方"绿涨红跌"相反。此处刻意与 K 线图、指数卡片的涨跌幅配色保持一致，避免用户认知冲突。全局配色规范：利好/上涨=红 `#f5222d`，利空/下跌=绿 `#52c41a`。

#### 验收标准

- 新闻流实时滚动，新消息自动出现在顶部
- 情感颜色标记正确（红/绿/灰）
- 按"标的筛选"仅显示相关股票新闻
- 来源筛选支持"境外"类别
- K 线图上显示重大新闻标记，悬停可见标题

---

### 阶段 3 整体数据流

```
                     Celery Beat 定时触发
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       国内新闻(10-30min)    境外新闻(08:00/17:00)    FinBERT 推理
              │             │                    (自动链式触发)
              └─────────────┼─────────────┘
                            │
                            ▼
                     news_raw 表
                     → 自动去重 + 翻译（境外需 Qwen3B 翻译）
                            │
                            ▼
                    FinBERT-zh 批量推理
                    → emotion_label / score
                            │
                     ┌──────┴──────┐
                     ▼             ▼
              news_raw 更新     factor_daily
              (情感标签)        (舆情因子聚合)
                                     │
                                     ▼
                              Stock Screener
                              (含跨境情绪因子：US_MARKET_SENTIMENT 等)
                                     │
                                     ▼
                           ┌──────────┴──────────┐
                           ▼                     ▼
                    News 前端页面          KLine 事件标记
                    (含境外来源筛选)       (重大新闻叠加)
```

| 任务 | 预估工时 | 依赖 |
|------|----------|------|
| T3.1 新闻抓取服务 | 8h | T0.2 |
| T3.2 FinBERT 批量推理 | 6h | T3.1, T0.5 |
| T3.3 舆情因子接入选股器 | 3h | T3.2, T2.3 |
| T3.4 新闻列表前端 | 8h | T3.2, T1.5 |
| **阶段合计** | **~25h（并行后约 17h）** | |

> T3.1 抓取服务可与 T3.2 FinBERT 部署并行开发（数据模型需先对齐）。
>
> **版本：V1.0** — 国内新闻抓取 + FinBERT 情感分析
> **V1.1** — 境外新闻 + 翻译流水线（本期不实现）

### 阶段 3 验收清单

| 编号 | 验收项 | 验证方式 |
|------|--------|----------|
| 3.1 | 每小时抓取 ≥ 200 条新闻 | `SELECT count(*) FROM news_raw WHERE crawl_time > NOW() - INTERVAL '1 hour'` |
| 3.1 | 境外新闻抓取 | 每天 08:00 + 17:00 定时触发抓取 CNBC/Reuters |
| 3.1 | 境外新闻翻译 | 抓取后 Qwen3B 自动翻译为中文 |
| 3.2 | FinBERT 部署可用 | `predict_batch(["利好"])` → label=positive |
| 3.2 | 100 条推理 < 30 秒 | 批量推理计时 |
| 3.2 | 新闻自动打标 | 抓取后 sentiment_label 自动填充 |
| 3.3 | 舆情因子出现在选股条件 | 选股器 UI 可选 `POSITIVE_NEWS_1D` 等因子 |
| 3.3 | 选股结果含舆情因子影响评分 | 比较权重调节前后排序变化 |
| 3.4 | 新闻流实时滚动 | 新消息出现在列表顶部 |
| 3.4 | 情感色标正确 | 红 = 正面（利好）、绿 = 负面（利空）、灰 = 中性（与 A 股配色一致） |
| 3.4 | 标的筛选 | 输入代码 "000001.SZ" 仅显示相关新闻 |
| 3.4 | K 线事件标记 | 重大新闻在 K 线图上显示为标记点 |

---

## 阶段 4：风控与 AI 交互增强

### 概述

本阶段构建系统的风控与 AI 交互能力。包括持仓管理、硬性止损检测、AI 选股解释与对话问答、策略回测，以及全系统性能优化。目标：实现持仓风险的主动监控告警，提供 AI 交互式分析体验，并验证策略的历史有效性。

### 系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Celery Workers                               │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │ RiskGuard       │  │ Backtest     │  │ Portfolio P&L Calc    │  │
│  │ 止损检测 (10s)  │  │ 回测计算      │  │ 持仓盈亏定时计算      │  │
│  └────────┬────────┘  └──────────────┘  └────────────────────────┘  │
└───────────┼──────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ /portfolio   │  │ /risk/alerts │  │ /ai/explain│  │ /backtest │  │
│  │ 持仓 CRUD    │  │ 告警查询     │  │ /ai/chat   │  │ 回测      │  │
│  └──────────────┘  └──────────────┘  └────────────┘  └───────────┘  │
└──────────────────────────────────────────────────────────────────────┘
            │
      ┌─────┼─────┐
      ▼     ▼     ▼
┌────────┐┌────────┐┌────────────────┐
│  Web    ││  TTS  ││  Ollama        │
│  Socket ││ 语音  ││  Qwen2.5-14B  │
│ 告警推送 ││ 播报  ││ AI 解释/对话  │
└────────┘└────────┘└────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          Frontend                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐  │
│  │ Portfolio   │  │ Risk Alerts  │  │ AI 助手    │  │ Backtest  │  │
│  │ 持仓管理    │  │ 告警面板     │  │ 对话浮窗    │  │ 回测结果  │  │
│  └──────────────┘  └──────────────┘  └────────────┘  └───────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

### T4.1 持仓管理模块

#### 目标

实现虚拟持仓的 CRUD 接口，后端定时计算盈亏，首页实时展示持仓盈亏状态。

#### 表结构

```sql
CREATE TABLE portfolio (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT        NOT NULL DEFAULT 'default',
    symbol        TEXT        NOT NULL,                -- 股票代码
    name          TEXT        NOT NULL,                -- 股票名称
    cost_price    NUMERIC(10,2) NOT NULL,              -- 成本价
    volume        INTEGER     NOT NULL,                -- 持仓股数
    add_time      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, symbol)
);

-- 定时计算快照
CREATE TABLE portfolio_snapshot (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT        NOT NULL DEFAULT 'default',
    symbol        TEXT        NOT NULL,
    current_price NUMERIC(10,2),
    pnl           NUMERIC(12,2),                       -- 盈亏金额
    pnl_pct       NUMERIC(6,4),                        -- 盈亏百分比
    snapshot_time TIMESTAMPTZ DEFAULT NOW()
);
```

#### API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/portfolio` | 持仓列表（含实时盈亏） |
| POST | `/api/v1/portfolio` | 添加持仓 |
| PUT | `/api/v1/portfolio/{id}` | 修改持仓 |
| DELETE | `/api/v1/portfolio/{id}` | 删除持仓 |
| GET | `/api/v1/portfolio/pnl` | 总盈亏汇总 |

#### 前端页面

```
frontend/src/pages/Portfolio/
├── index.tsx                    # 持仓管理页面
├── components/
│   ├── PortfolioTable.tsx       # 持仓列表（含盈亏列）
│   ├── AddPositionModal.tsx     # 添加持仓弹窗
│   └── PnlSummary.tsx           # 盈亏汇总卡片
└── hooks/
    └── usePortfolio.ts          # 持仓数据 Hook
```

#### 首页集成

在 Dashboard 中增加持仓盈亏摘要卡片：

```
┌──────────────────────────────────────┐
│  总市值: ¥125,800     总盈亏: +¥8,500 │
│  今日收益: +¥1,200 (+0.96%)          │
│  ┌──────┬────────┬──────┬────────┐  │
│  │ 平安  │ ¥11.25 │ +2.3% │ ¥2,250│  │
│  │ 茅台  │ ¥1,580 │ -0.5% │ -¥800 │  │
│  └──────┴────────┴──────┴────────┘  │
└──────────────────────────────────────┘
```

#### 自选股分组

持仓支持自定义分组管理：

```json
// POST /api/v1/portfolio/groups
{
  "name": "核心持仓",
  "description": "长期持有重点关注"
}
// PUT /api/v1/portfolio/{id} — 添加 group_id 字段
{
  "symbol": "000001.SZ",
  "name": "平安银行",
  "cost_price": 10.50,
  "volume": 1000,
  "group_id": 1        // 所属分组
}
```

- 首页自选股表格上方显示分组 Tab 切换：`[核心持仓] [观察池] [短线标的] [全部]`
- 风控引擎可按分组配置不同止损策略（核心持仓止损宽松，短线标的止损严格）

#### 验收标准

- 添加持仓后，持仓列表显示股票和成本价
- 支持自选股分组（核心持仓 / 观察池 / 短线标的），首页分组切换
- 首页盈亏随实时行情自动更新
- 总盈亏 = Σ(现价 - 成本价) × 股数

---

### T4.2 硬性止损与技术破位检测

#### 目标

RiskGuard 引擎实时检测持仓风险，支持价格止损、均线跌破、趋势线破位、资金大幅流出等场景，触发后推送桌面通知并语音播报。

#### 检测规则

> ⚠️ **两层风控，不要混跑**：只有「价格止损」是**盘中实时**信号，应订阅实时行情流实时判断（10s 级轮询即可）；其余规则（均线跌破 / 技术破位 / 资金异常 / 舆情急跌）都来自**日频 EOD 因子**，应在每天 **15:30 盘后因子计算**时触发一次，无需在 10s 扫描里反复判断，既省资源又语义正确。

| 层级 | 规则 | 触发条件 | 数据源 | 触发时机 |
|------|------|----------|--------|----------|
| 实时 | **价格止损** | 最新价 ≤ 止损价（用户设置） | 实时行情流 | 盘中订阅行情，实时判断 |
| 盘后 | **均线跌破** | 收盘价跌破 MA20 / MA60 | 日 K 线 | 15:30 盘后因子计算 |
| 盘后 | **技术破位** | BOLL 下轨跌破 / MACD 死叉 | 因子计算 | 15:30 盘后因子计算 |
| 盘后 | **资金异常** | 主力资金净流出占比 > 5% | 资金因子 | 15:30 盘后因子计算 |
| 盘后 | **舆情急跌** | 负面新闻强度 > 0.8 且价格下跌 > 2% | 情感因子 | 15:30 盘后因子计算 |

#### RiskGuard 引擎设计

```python
class RiskGuard:
    """风控引擎，定时扫描持仓风险"""

    def __init__(self):
        self.rules: list[RiskRule] = [
            PriceStopLoss(threshold=0.95),      # 跌破成本价 95%
            MaBreakdown(ma_period=20),           # 跌破 MA20
            BollingerBreak(lower_band=True),     # 跌破布林下轨
            MacdDeathCross(),                    # MACD 死叉
            MainFundOutflow(threshold=0.05),     # 主力资金流出 > 5%
            NegativeSentiment(intensity=0.8),    # 负面舆情 + 跌 2%
        ]

    async def scan(self, holdings: list[Position]) -> list[Alert]:
        """扫描全部持仓，返回触发的告警"""
        ...

    async def execute_alerts(self, alerts: list[Alert]):
        """执行告警：WebSocket 推送 + TTS 语音"""
        ...
```

#### 告警通道

```
┌──────────┐    ┌──────────────┐    ┌──────────────────┐
│ Risk     │───▶│ WebSocket    │───▶│ 桌面通知          │
│ Guard    │    │ /ws/market   │    │ (Ant Design 通知) │
│ (实时/盘后)│   │ type:"risk"  │    └──────────────────┘
│          │    └──────────────┘
│          │    ┌──────────────┐    ┌──────────────────┐
│          │───▶│ 前端浏览器    │───▶│ 语音播报          │
│          │    │ Web Speech / │    │ "XX 股票止损触发" │
│          │    │ edge-tts     │    └──────────────────┘
└──────────┘    └──────────────┘
```

> ⚠️ **TTS 放前端，不放后端**：后端跑在 WSL2，没有音频设备，`pyttsx3`/espeak 无法播到 Windows 桌面。改为**前端浏览器用 Web Speech API（`SpeechSynthesis`，`zh-CN` 嗓音）**合成播报；若对音质有要求，后端用 `edge-tts` 生成音频流、前端播放。告警语音由浏览器合成最合理。后端 `tts.py` 仅作为可选的音频生成封装，不参与主链路。

#### 通知消息格式

```json
{
  "type": "risk_alert",
  "data": {
    "symbol": "000001.SZ",
    "name": "平安银行",
    "rule": "price_stop_loss",
    "message": "平安银行 11.25 已跌破止损线 11.40",
    "severity": "critical",       // critical / warning / info
    "timestamp": "2026-06-04T10:30:00Z"
  }
}
```

#### 文件清单

```
backend/app/services/risk_guard.py         # RiskGuard 引擎主逻辑
backend/app/services/rules/
├── __init__.py
├── price_stop_loss.py          # 价格止损规则
├── ma_breakdown.py             # 均线跌破规则
├── bollinger_break.py          # 布林带破位规则
├── macd_death_cross.py         # MACD 死叉规则
├── fund_outflow.py             # 资金流出规则
└── negative_sentiment.py       # 负面舆情规则
backend/app/services/tts.py                # TTS 语音播报封装
```

#### 自定义止损规则

用户可通过 UI 创建自定义止损规则组合：

```json
// POST /api/v1/risk/rules
{
  "name": "我的激进止损",
  "conditions": [
    {"rule": "price_drop", "params": {"threshold": 5}},           // 价格跌 5%
    {"rule": "volume_spike", "params": {"ratio": 2.0}},           // 成交量放大 200%
    {"rule": "ma_break", "params": {"period": 20}},               // 跌破 MA20
    {"rule": "main_flow", "params": {"threshold": 3}}             // 主力流出 > 3%
  ],
  "logic": "OR",                                                   // 任一条件触发即告警
  "action": "notification + tts",                                  // 推送 + 语音
  "valid_days": 30,                                                // 有效期
  "severity": "warning"
}
```

支持的规则条件库 (`backend/app/services/rules/`) 保持可扩展，新增规则只需实现 `RiskRule` 接口：

```python
class RiskRule(ABC):
    @abstractmethod
    async def check(self, position: Position, market_data: dict) -> Optional[Alert]:
        """检查是否触发，触发返回 Alert，否则返回 None"""
        ...
```

#### 验收标准

- 模拟持仓某股票现价跌破止损价，WebSocket 收到 `risk_alert` 消息
- 桌面弹出 Ant Design 通知
- 前端浏览器语音播报："平安银行已触发止损，当前价 11.25，止损线 11.40"（Web Speech / edge-tts）

---

### T4.3 AI 选股解释与复盘对话

#### 目标

实现 AI 驱动的选股原因解释和 Qwen2.5-14B 对话接口，辅助用户理解选股逻辑和市场动态。

#### API 设计

```json
// 选股解释
GET /api/v1/ai/explain/{symbol}?date=2026-06-04

// 响应
{
  "symbol": "000001.SZ",
  "name": "平安银行",
  "explanation": "平安银行当前满足以下条件入选：\n"
                "1. **均线多头排列** — MA5(11.20) > MA10(11.10) > MA20(10.95)，短期趋势向上\n"
                "2. **MACD金叉** — DIF(0.25) 上穿 DEA(0.18)，动能增强\n"
                "3. **北向资金持续流入** — 近5日净流入12.5亿元，外资看好\n"
                "4. **板块共振** — 银行板块近3日涨幅2.5%，板块热度排名前5\n\n"
                "综合评分 85.3 分，属强势股。",
  "score": 85.3,
  "key_factors": ["均线多头", "MACD金叉", "北向流入", "板块共振"]
}


// 对话接口
POST /api/v1/ai/chat
{
  "message": "今天为什么AI板块大涨？",
  "context": {
    "date": "2026-06-04",
    "market_data": {...}  // 可选上下文
  }
}

// 响应（流式 SSE）
{
  "message": "今日AI板块大涨主要受以下因素驱动：\n"
             "1. **政策催化** — 工信部今日发布《人工智能产业促进计划》...\n"
             "2. **资金推动** — 北向资金今日净买入AI板块超20亿元...\n"
             "3. **龙头带动** — 寒武纪、中科曙光等龙头涨幅超过7%...\n"
             "4. **情绪共振** — 隔夜英伟达大涨5%，提振全球AI信心..."
}
```

#### 文件清单

```
backend/app/services/ai_explainer.py     # 选股解释服务（结构化数据 → Prompt → LLM）
backend/app/services/ai_chat.py          # 对话服务（带市场上下文）
backend/app/prompts/
├── explain_prompt.txt                   # 选股解释 Prompt 模板
└── chat_prompt.txt                      # 对话 Prompt 模板
backend/app/api/v1/ai.py                 # AI 路由
```

#### 前端 AI 助手浮窗

```
frontend/src/components/AIAssistant/
├── index.tsx                    # AI 助手浮窗组件（右下角固定）
├── components/
│   ├── ChatPanel.tsx            # 对话面板
│   └── ExplanationCard.tsx      # 选股解释卡片
└── hooks/
    └── useAIChat.ts             # SSE 流式聊天 Hook
```

- 右下角浮动图标，点击展开对话面板
- 支持流式响应（SSE），打字机效果
- 在看个股详情页时，"AI 解释"按钮触发选股解释

#### 验收标准

```bash
# 选股解释
curl http://localhost:8000/api/v1/ai/explain/000001.SZ
# 返回因子分析和自然语言理由

# 对话
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "今天为什么AI板块大涨？"}'
# 返回有逻辑的分析，包含实际数据和原因
```

---

### T4.4 策略回测系统（简单版）

#### 目标

实现基于历史因子数据的策略回测引擎，支持选股条件作为策略输入，输出收益率曲线和绩效指标。

#### 回测引擎设计

```
┌─────────────────────────────────────────────────────────────┐
│                     Backtester                                │
│                                                              │
│  输入: 选股条件 + 时间范围 + 调仓频率                           │
│                                                              │
│  流程:                                                       │
│  1. 按日/周遍历时间窗口                                       │
│  2. 每个窗口日：从 DuckDB (或 factor_daily) 筛选符合条件的股票  │
│  3. 等权买入 Top N，记录持仓                                   │
│  4. 下个窗口日：调仓（卖出旧仓、买入新仓）                      │
│  5. 计算每日组合净值                                           │
│                                                              │
│  输出:                                                        │
│  • 累计收益率 / 年化收益率                                     │
│  • 夏普比率 / 最大回撤 / 回撤区间                               │
│  • 月度胜率 / 交易次数                                         │
│  • 净值曲线（每日）                                            │
│  • 与基准（沪深300）对比                                       │
└─────────────────────────────────────────────────────────────┘
```

> 回测引擎默认使用 DuckDB 进行历史因子分析查询（列存加速，非纯净系统下按需加载内存，用完即释放）。

> ⚠️ **回测正确性约束（必须满足，否则结论不可信）**：
> 1. **禁止前视偏差**：因子在 `t` 日**收盘**计算，信号只能在 `t+1` 日**开盘**成交，绝不能用当日收盘价买入当日信号股。
> 2. **Point-in-time 可交易集合**：历史选股必须按 `上市日期 ≤ t` 且 `未退市` 过滤，不能用"当前全市场 5000 只"回测过去（否则幸存者偏差，结果被严重高估）。
> 3. **交易成本**：单边佣金约 0.03% + 印花税 0.05%（卖出收）+ 滑点（建议 0.1%~0.2%），净值必须扣除，否则收益虚高。
> 4. **涨停无法买入 / 跌停无法卖出**：成交价触及涨跌停时该日实际无法成交，应跳过或顺延。

#### API 设计

```json
POST /api/v1/backtest
{
  "strategy": {
    "conditions": [
      {"factor": "MA_CROSS", "op": "eq", "value": "多头排列"},
      {"factor": "RSI_14", "op": "between", "value": [30, 70]}
    ],
    "logic": "AND",
    "top_n": 10,
    "rebalance_freq": "weekly"       // daily / weekly / monthly
  },
  "start_date": "2023-01-01",
  "end_date": "2025-12-31",
  "benchmark": "000300.SH"           // 沪深300
}

// 响应
{
  "summary": {
    "total_return": 85.32,
    "annual_return": 22.15,
    "sharpe_ratio": 1.85,
    "max_drawdown": -12.5,
    "max_drawdown_period": "2024-01-15 ~ 2024-02-05",
    "win_rate": 62.3,
    "total_trades": 156
  },
  "nav_series": [
    {"date": "2023-01-01", "strategy": 1.0, "benchmark": 1.0},
    {"date": "2023-01-08", "strategy": 1.023, "benchmark": 1.015},
    ...
  ],
  "monthly_returns": {
    "2023-01": 3.2,
    "2023-02": -1.5,
    ...
  }
}
```

#### 文件清单

```
backend/app/services/backtester.py        # 回测引擎核心
backend/app/api/v1/backtest.py            # 回测 API
backend/app/services/backtest_cache.py    # 回测结果缓存（避免重复计算）

frontend/src/pages/Backtest/
├── index.tsx                    # 回测页面
├── components/
│   ├── BacktestForm.tsx         # 回测参数表单
│   ├── NavChart.tsx             # 净值曲线图（ECharts）
│   ├── MetricsCards.tsx         # 绩效指标卡片
│   └── MonthlyHeatmap.tsx       # 月度收益热力图
└── hooks/
    └── useBacktest.ts           # 回测请求 Hook
```

#### 前端页面布局

```
┌──────────────────────────────────────────────────────────────────┐
│  策略回测                                                          │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐     │
│  │  回测参数                                                │     │
│  │  条件: [均线排列=多头] [RSI=30~70]    Top N: [10]       │     │
│  │  起始: [2023-01-01]  结束: [2025-12-31]  调仓: [每周]   │     │
│  │                                             [开始回测]  │     │
│  └────────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────┬──────────┬──────────┬──────────┬──────────────┐  │
│  │ 累计收益  │ 年化收益  │ 夏普比率  │ 最大回撤  │ 胜率        │  │
│  │ +85.32%  │ +22.15%  │ 1.85     │ -12.50%  │ 62.3%       │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐     │
│  │  净值曲线（策略 vs 沪深300）                            │     │
│  │  ┌────────────────────────────────────────────────┐   │     │
│  │  │  📈 ████████████████████████████████████████  │   │     │
│  │  │  ── 策略  ── 沪深300                           │   │     │
│  │  └────────────────────────────────────────────────┘   │     │
│  └────────────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────┐     │
│  │  月度收益热力图                                          │     │
│  │      01月 02月 03月 04月 05月 06月 ...                   │     │
│  │  2023  +3.2 -1.5 +2.1 -0.8 +5.3 +3.7                   │     │
│  │  2024  +4.1 +2.3 -3.2 +1.5 +2.8 +4.5                   │     │
│  │  🟢=盈利  🔴=亏损  色深=幅度大                          │     │
│  └────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

#### 验收标准

```bash
curl -X POST http://localhost:8000/api/v1/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy":{"conditions":[{"factor":"MA_CROSS","op":"eq","value":"多头排列"}],"top_n":10,"rebalance_freq":"weekly"},"start_date":"2023-01-01","end_date":"2025-12-31"}'
# 返回净值序列和绩效指标

# 前端展示：净值曲线 + 4 个指标卡片 + 月度热力图
```

---

### T4.5 整体联调与性能优化

#### 目标

全系统集成测试，优化关键性能瓶颈，保证盘中流畅运行。

#### 优化项

| 领域 | 优化项 | 预期效果 |
|------|--------|----------|
| **TimescaleDB** | 添加复合索引 `(symbol, trade_date)`；分区大小调优；压缩策略确认生效 | 查询速度 < 50ms |
| **Redis** | Stream 消息设置 TTL（7天）；限制消费者组数量 | 内存使用降低 30% |
| **后端** | WebSocket 连接数上限配置；Celery Worker 并发数调优 | 支持 100+ 并发连接 |
| **前端** | 虚拟滚动（react-window）大列表；WebSocket 消息去重；ECharts 懒加载 | 列表渲染 < 100ms |
| **LLM** | 设置 Ollama 并发请求队列（max 2）；请求超时 30s | 避免 GPU OOM |

#### 测试场景

| 场景 | 条件 | 预期 |
|------|------|------|
| 盘中高负载 | 同时打开 Dashboard + 自选股 + 新闻流 | 页面不卡顿，FPS > 30 |
| 大量持仓 | 30 只持仓股票实时盈亏计算 | 盈亏更新延迟 < 1s |
| 并发选股 | 5 个请求同时调用 screener | 全部在 3s 内返回 |
| 长时间运行 | 连续运行 8 小时 | 内存无泄漏，日志无异常 |
| 断线恢复 | 关闭 Redis 30 秒后重启 | 网关自动重连，数据不丢失 |

#### 产出

- 性能测试报告（含各接口响应时间、内存/CPU 占用、FPS）
- 优化 commit 记录

#### 验收标准

- 所有性能测试场景达标
- 盘中最重页面（Dashboard）FPS ≥ 30
- 连续运行 8 小时后，内存占用无持续上涨

#### 数据质量检查（每日自动）

数据源抖动是 A 股量化系统的常见问题（akshare 超时、Tushare 限流、复权未处理）。增加每日盘后数据质量检查任务：

```python
# backend/app/tasks/data_quality.py — 每天 16:15 执行
@celery.task
def check_data_quality():
    """检查当日数据质量并记录"""
    checks = {
        "stock_count":            "SELECT count(*) FROM stock_daily WHERE trade_date = TODAY",
        "abnormal_pct":           "SELECT count(*) FROM stock_daily WHERE abs(pct_change) > 20",
        "missing_ratio":          "按行业统计缺失比例",
        "source_response_time":   "来自爬虫日志的接口响应时间",
    }
    results = {name: db.execute(sql) for name, sql in checks.items()}
    # 写入 data_quality 表
    # 异常指标（如缺失率 > 5%）通过 WebSocket 推送到前端数据质量看板
```

该检查默认只记录日志和入库，不阻塞其他流程。当数据缺失率超过阈值时，在 Dashboard 顶部展示警告条。

---

### 阶段 4 整体数据流

```
                         ┌─────────────────┐
                         │    Ollama       │
                         │  Qwen2.5-14B   │
                         └──┬──┬──┬───────┘
                            │  │  │
                ┌───────────┘  │  └───────────┐
                ▼              ▼              ▼
         AI 解释         AI 对话         RiskGuard
         因子数据 →      市场问答        Prompt 判断
        自然语言理由      SSE 流式       (是否触发告警)
                │              │              │
                └──────┬───────┘              │
                       │                      ▼
                       │              ┌──────────────┐
                       │              │  TTS 语音    │
                       │              │  告警播报    │
                       │              └──────────────┘
                       ▼
              ┌──────────────────┐
              │  FastAPI         │
              │  /ai/* /backtest │
              │  /portfolio      │
              │  /risk/*         │
              └──────────────────┘
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         Portfolio  Factor    TimescaleDB
         持仓表     Daily     回测数据
```

---

### 依赖关系与并行策略

```
T4.1 持仓管理 ──┬── T4.2 RiskGuard 风控
                 │
T4.3 AI 交互 ────┤
                 │
T4.4 策略回测 ───┘
                 │
            T4.5 联调优化
```

| 任务 | 预估工时 | 依赖 |
|------|----------|------|
| T4.1 持仓管理模块 | 6h | T1.2, T1.4 |
| T4.2 RiskGuard 风控 | 8h | T4.1, T1.4 |
| T4.3 AI 选股解释与对话 | 8h | T0.5, T2.3 |
| T4.4 策略回测 | 12h | T2.1, T2.2, T1.2 |
| T4.5 联调优化 | 8h | 所有主要模块 |
| **阶段合计** | **~42h（并行后约 28h）** | |

> T4.1/T4.3/T4.4 三者可并行开发。T4.2 依赖 T4.1。
>
> **版本**：T4.2 预设 5 条规则为 V1.0，自定义规则 UI 构建器归入 V1.1。

---

### 全项目工时汇总

| 阶段 | 任务数 | 预估总工时 | 并行后实际 | 累计工时 |
|------|--------|-----------|-----------|---------|
| 阶段 0：环境与基础设施 | 5 | 9h | ~5h | ~5h |
| 阶段 1：MVP 行情看板 | 6 | 31h | ~20h | ~25h |
| 阶段 2：选股引擎与复盘 | 6 | 42h | ~28h | ~53h |
| 阶段 3：舆情与情绪引擎 | 4 | 25h | ~17h | ~70h |
| 阶段 4：风控与 AI 交互 | 5 | 42h | ~28h | ~98h |
| **全项目合计** | **26** | **~149h** | **~98h** | |

> 按每天 6 小时有效开发时间计算，全工期约 **16~17 个工作日**，约 **3~3.5 周**。

---

### 阶段 4 验收清单

| 编号 | 验收项 | 验证方式 |
|------|--------|----------|
| 4.1 | 持仓 CRUD 可用 | 添加/修改/删除持仓后列表同步更新 |
| 4.1 | 持仓分组管理 | 创建分组后 Tab 切换正常 |
| 4.1 | 首页盈亏实时更新 | 盈亏数值随行情变化 |
| 4.2 | 价格止损检测生效 | 模拟跌破止损价，WebSocket 收到告警 |
| 4.2 | 自定义止损规则 | 创建组合规则后条件触发告警 |
| 4.2 | TTS 语音播报 | 止损触发时听到语音播报 |
| 4.2 | 均线破位检测 | 收盘价跌破 MA20 触发告警 |
| 4.2 | 桌面通知弹出 | Ant Design 通知组件出现 |
| 4.3 | AI 选股解释 | `GET /ai/explain/000001.SZ` 返回因子分析和理由 |
| 4.3 | AI 对话接口 | `POST /ai/chat` "今天AI板块为什么涨" 返回合理分析 |
| 4.3 | 前端 AI 助手浮窗 | 右下角浮动图标可展开对话面板 |
| 4.3 | SSE 流式响应 | 对话内容逐字输出（打字机效果） |
| 4.4 | 回测返回净值序列 | `POST /backtest` 返回 `nav_series` 数组 |
| 4.4 | 回测指标完整 | 含累计收益、年化、夏普、最大回撤、胜率 |
| 4.4 | 净值曲线图渲染 | ECharts 展示策略 vs 基准对比曲线 |
| 4.4 | 月度收益热力图 | 月度收益率矩阵色块图 |
| 4.5 | Dashboard FPS ≥ 30 | 浏览器 DevTools Performance 面板 |
| 4.5 | 8 小时无内存泄漏 | 监控 RSS 内存无持续增长 |
| 4.5 | Redis 断线自动重连 | 关闭 Redis 30s 后重启，网关自动恢复 |

---

## 版本策略：V1.0 / V1.1 拆分

为控制复杂度、保障 6 周内交付可用的完整系统，将功能拆分为两个版本。

### V1.0 核心闭环（1-6 周）

V1.0 目标是跑通"数据 → 行情 → 选股 → 风控 → 报告"全链路，覆盖核心交易场景。

| 阶段 | V1.0 包含 | V1.0 排除（延至 V1.1） |
|------|-----------|----------------------|
| **阶段 0** | 全部（WSL2 + 数据库 + 骨架 + Ollama） | — |
| **阶段 1** | 全部（行情网关单进程、自选股分组简化版） | 多进程网关改造 |
| **阶段 2** | 全部（含 DuckDB 路由、预设因子、邮件推送） | 对比模式、因子雷达图 |
| **阶段 3** | 国内新闻抓取 + FinBERT 情感分析 | 境外新闻、翻译流水线 |
| **阶段 4** | 持仓管理 + 分组 + 预设 5 条止损规则 + DuckDB 回测 | 自定义规则 UI 构建器 |

**V1.0 工时估计**：~80h（~13 个工作日，约 2.5 周并行后）

### V1.1 锦上添花（7-10 周）

| 功能 | 工时 | 前置依赖 |
|------|------|----------|
| 境外新闻抓取 + 展示（英文情感分类） | 6h | T3.1 基础版完成 |
| 翻译流水线（Ollama 翻译） | 8h | 境外新闻上线 |
| 对比模式 + 因子雷达图（前端） | 4h | T2.4 基础版完成 |
| 自定义止损规则 UI 构建器 | 8h | T4.2 预设规则上线 |
| 多进程行情网关（可选优化） | 6h | T1.3 单进程稳定运行后 |

**V1.1 工时估计**：~32h

### 版本时间线

```
Week 1-2     Week 3-4     Week 5-6     Week 7-8     Week 9-10
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  阶段 0   │ │  阶段 1   │ │  阶段 2   │ │  阶段 3   │ │  阶段 4   │
│  环境     │ │  行情     │ │  选股     │ │  国内舆情 │ │  风控     │
│  骨架     │ │  Dashboard│ │  报告     │ │  FinBERT │ │  回测     │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
                                                      ┌──────────┐
                                                      │  联调优化 │
                                                      └──────────┘
═══════════════ V1.0 交付 ═══════════════║
                                          ┌──────────┐ ┌──────────┐
                                          │  境外新闻 │ │  对比模式 │
                                          │  翻译     │ │  自定义   │
                                          └──────────┘ │  止损规则 │
                                                       └──────────┘
                                          ═══════════════ V1.1 ═══════║
```

### 各任务 V1.0/V1.1 标记

| 任务 | 版本 | 说明 |
|------|------|------|
| T0.1 T0.2 T0.3 T0.4 T0.5 | V1.0 | 基础设施，全部必做 |
| T1.1 T1.2 T1.3 T1.4 T1.5 T1.6 | V1.0 | MVP 核心链路 |
| T2.1 T2.2 T2.3 | V1.0 | 因子库 + 选股核心 |
| T2.4（基础选股UI） | V1.0 | 条件构建 + 结果表格 |
| T2.4（对比模式） | **V1.1** | 多股 K 线叠加 + 雷达图 |
| T2.5 T2.6 | V1.0 | 复盘报告生成 + 展示 |
| T3.1（国内新闻） | V1.0 | 国内三源 |
| T3.1（境外新闻） | **V1.1** | CNBC/Reuters 等 + 翻译 |
| T3.2 T3.3 | V1.0 | FinBERT + 舆情因子 |
| T3.4 | V1.0 | 新闻流（国内） |
| T4.1 T4.4 | V1.0 | 持仓 + DuckDB 回测 |
| T4.2（预设规则） | V1.0 | 5 条内置止损规则 |
| T4.2（自定义规则UI） | **V1.1** | 规则条件构建器 |
| T4.3 | V1.0 | AI 解释 + 对话 |
| T4.5 | V1.0 | 联调优化 |

### 关键决策记录

| 决策 | 结论 | 理由 |
|------|------|------|
| WSL2 processors | 8 核 | 盘后并行任务多，4 核瓶颈 |
| PG effective_cache_size | 8GB（非 12GB） | 与 Redis/Ollama/系统共享 24GB |
| DuckDB 数据同步 | postgres_scanner 直查 PG，无需 ETL | 零维护、实时 |
| 境外新闻 | V1.1 | 翻译流水线复杂度高 |
| 自定义止损规则 | V1.1 完整版，V1.0 预设规则 | 规则构建器 UI 工作量大 |
| 对比模式 | V1.1 | 纯前端功能，不影响核心闭环 |
| 数据质量检查 | V1.0（轻量版，仅日志+警告条） | 数据源抖动是常态，早期发现价值大 |
| 配置管理 | config.yaml + .env 统一管理 | 参数增多后的必然要求 |
