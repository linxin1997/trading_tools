# Docker 使用必要性分析 — trading_tools

> 分析视角：Windows 11 + WSL2(Ubuntu 22.04) + RTX 5080 单机、个人本地量化工具。
> 结论先行：**Docker 在本项目中非必要，但作为"数据层便利包"是合理且低成本的；真正该修的是数据卷挂载位置（/mnt/d 是性能坑），而不是纠结要不要用 Docker。**

---

## 1. 现实盘点：Docker 在你这里到底干了什么

| 组件 | 运行方式 | 是否在 Docker |
|------|----------|---------------|
| TimescaleDB (PG16) | `timescale/timescaledb:2-pg16` 容器 | ✅ 是 |
| Redis 7 | `redis:7-alpine` 容器 | ✅ 是 |
| FastAPI 后端 | WSL2 原生 `uvicorn` | ❌ 否 |
| React 前端 | WSL2 原生 `vite` | ❌ 否 |
| Celery worker/beat | WSL2 原生进程 | ❌ 否 |
| Ollama (qwen2.5 3B/14B) | WSL2 原生 + GPU 直通 | ❌ 否 |

compose 文件共 **39 行**，只有 `timescaledb` + `redis` 两个 service，且**没有任何 `gpus`/`nvidia`/`deploy` 配置**——GPU 相关组件根本不在容器里。

→ 所以"用 Docker"对你而言，等价于"用容器跑 Postgres 和 Redis 两个有状态服务"。

---

## 2. Docker 在这里真正解决的价值（值得保留的部分）

| 价值 | 说明 | 对个人项目的真实分量 |
|------|------|----------------------|
| **版本钉死** | `2-pg16` / `7-alpine` 精确锁定。WSL2 原生 `apt` 装 PG 只会给 Ubuntu 22.04 仓库的 PG14，TimescaleDB 还得单独加官方 apt 源。 | ⭐⭐⭐ 省心，确实有价值 |
| **一键启停 + 自动建库** | `docker compose up -d` 同时拉起两个服务，并把 `init.sql` 自动挂进 `initdb.d` 执行。原生装要手动 initdb、跑 init.sql、配 `postgresql.conf`。 | ⭐⭐⭐ 显著提升开发体验 |
| **干净重置** | `docker compose down -v` 一键清空重来，适合反复试错。 | ⭐⭐⭐ 量化系统天天改 schema，极实用 |
| **不污染 WSL2 系统包** | 设计文档明确写了"非纯净系统适配"——容器不往 Ubuntu 里塞 PG/Redis。 | ⭐⭐ 符合你已有的偏好 |
| **数据持久化** | 卷挂载保证容器重建后数据还在。 | ⭐⭐ 但挂载点选错了（见第 4 节） |

---

## 3. Docker "本应"的价值，在这里为什么用不上

| 容器化经典卖点 | 本项目是否用得上 | 原因 |
|----------------|------------------|------|
| 跨机器可移植 / 部署一致 | ❌ 用不上 | 单台固定机器，从不在别处部署 |
| 横向扩展 / 多副本 | ❌ 用不上 | 个人单机，Redis/PG 各 1 个实例，无扩缩容 |
| 多服务编排编排 | ⚠️ 半用 | 只编排了 2 个数据服务，app/worker 都是原生进程，没真正"全编排" |
| GPU 算力随容器调度 | ❌ 用不上 | Ollama 没容器化，Docker 的 GPU 优势在此项完全缺席 |
| 环境一致性（Linux vs Windows） | ⚠️ 半用 | WSL2 本身已是 Linux 沙盒，"要 Linux"已由 WSL2 满足，Docker 只是在 WSL2 里再套一层 |

→ **核心结论**：你为 Docker 付出的复杂度（额外一层虚拟化、调试间接性），换来的全是"开发便利"，而不是"架构必需"。

---

## 4. 真实代价与当前配置的一个硬伤

### 4.1 资源开销（客观存在）
Windows 上的 Docker Desktop 本质是在 WSL2 之上再跑一个独立 Hyper-V/MIR VM。你 `.wslconfig` 已给 WSL2 限了 24GB 内存，Docker Desktop 会在其之上再加一层开销。Postgres+Redis 这点负载，原生装进 WSL2 反而比套 Docker 更省内存。

### 4.2 🔴 数据卷挂在 /mnt/d 是性能坑（最该改）
```yaml
volumes:
  - /mnt/d/code/project/trading_tools/data/timescale:/var/lib/postgresql/data
```
`/mnt/d` 是 Windows 文件系统经 **DrvFS** 挂载进 WSL2 的。数据库是大量小随机 I/O + fsync 负载，DrvFS 的延迟比 WSL2 原生 ext4（虚拟磁盘镜像）**高一个数量级**，且文件锁语义不同，长期跑有数据一致性隐忧。

**修复方式（保留 Docker 也能修）**：改用 Docker 命名卷（named volume），数据落在 WSL2 的 ext4 磁盘镜像里：
```yaml
volumes:
  - ts_data:/var/lib/postgresql/data   # 顶部 volumes: 声明 ts_data:
```
命名卷在 Windows 重启后同样持久，且性能正常。如果你非要能在 Windows 资源管理器里直接翻数据文件，再退而求其次挂到 WSL2 家目录（如 `~/trading_data/timescale`），也比 `/mnt/d` 强。

### 4.3 调试间接性
原生进程直接 `ps`/`journalctl` 可见；容器里多一层，排错要多敲 `docker logs`/`exec`。对个人单人开发，这点摩擦虽小但长期累积。

---

## 5. 必要性评分矩阵

| 维度 | Docker 当前贡献 | 裸机原生同等能做？ | 必要性 |
|------|----------------|--------------------|--------|
| 版本钉死 | 高 | 中（需手动加源） | 有益，非必需 |
| 一键启停/建库 | 高 | 中（写个 start.sh 即可） | 有益，非必需 |
| 干净重置 | 高 | 中（删 data 目录） | 有益，非必需 |
| 不污染主机 | 中 | 中（venv/隔离目录可替代） | 有益，非必需 |
| 跨机可移植 | 无 | — | 不适用 |
| 横向扩展 | 无 | — | 不适用 |
| GPU 友好 | 无（Ollama 未容器化） | 原生反而更简单 | 不适用 |
| 性能 | 负（/mnt/d 坑） | 原生更优 | 负收益 |
| 资源开销 | 负（额外 VM） | 原生更省 | 负收益 |

**综合判定**：Docker 在本项目的必要性 = **低（非必需）**，但**实用价值 = 中高（开发便利）**。属于"可用可不用、用了图省事"的便利层，不是架构基石。

---

## 6. 三种路线的对比与建议

| 路线 | 评价 | 建议 |
|------|------|------|
| **A. 保持现状（仅数据层用 Docker）** | 最稳，改动最小，已验证可跑 | ✅ **推荐**。但必须把 §4.2 的 `/mnt/d` 改成命名卷 |
| B. 全部原生（PG/Redis 也装进 WSL2） | 更省内存、性能更好，但初始化/重置要自己写脚本 | 可接受，但你已经配好 Docker，迁移收益不大 |
| C. 全容器化（backend/Celery/Ollama 也进容器） | 看似"标准"，实则最差：Ollama 需 NVIDIA Container Toolkit 才能用 GPU（复杂度飙升），vite/uvicorn 热重载在 WSL2 bind mount 下变慢，单人调试更烦 | ❌ 反对。把 Ollama 塞进容器尤其不划算 |

**关键反对点**：**不要为了"更标准"把 Ollama 容器化**。RTX 5080 的 GPU 直通在 WSL2 原生跑 Ollama 是最省事、最稳的路径；一旦进容器就要配 `--gpus all` + NVIDIA Container Toolkit + 驱动兼容，对单机个人工具是纯负担、零收益。

---

## 7. 我的具体行动建议（按性价比排序）

1. **【必做·改挂载】** 把 `timescaledb` 和 `redis` 的数据卷从 `/mnt/d/...` 改成 Docker 命名卷（或 WSL2 本地目录）。这一项直接消除性能与一致性隐患，且完全保留现状的便利。**改动 < 5 行，收益最大。**
2. **【保持】** Docker 继续只管数据层（TimescaleDB + Redis），这是甜区。
3. **【保持】** 后端 / Celery / 前端 / Ollama 全部原生跑在 WSL2，不进容器。
4. **【可选】** 如果哪天想"一条命令拉起整套环境"，可以加一个 `Makefile` 或 `start.sh`：先 `docker compose up -d`，再并行启动 uvicorn / celery / vite / ollama pull——这比把 app 塞进容器优雅得多。
5. **【不必做】** 不用为了"工程化"强行全容器化。对个人单机量化工具，过度容器化是反模式。

---

## 8. 一句话总结

> **Docker 对你不是"要不要"的架构问题，而是"图不图省事"的便利选择。** 它当前只帮你跑 Postgres 和 Redis，价值真实但非必需；真正该做的是把数据卷从 Windows 侧的 `/mnt/d` 挪回 WSL2 的 ext4（命名卷），别让"为了用 Docker"反而吃下性能与一致性坑。Ollama 和后端请留在原生 WSL2——尤其是 GPU 那块，原生才是正道。
