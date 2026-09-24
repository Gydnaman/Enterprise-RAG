# 架构脊柱评审：Enterprise RAG Workbench

- **结论：修改后再通过（Stage A 实现交接暂不通过）。** 这份脊柱已把 Stage A 的模块边界、mock/live 标识、证据溯源、运行事件与 SQLite/Compose 双模式写得相当清楚；但若直接作为实施基线，版本表会诱导使用过时依赖，Stage B 稳定端口没有完整落到架构决策里，且 DB 启动/迁移规则存在歧义。
- **评审范围：** `ARCHITECTURE-SPINE.md`，对照同目录 `SOLUTION-DESIGN.md` 与源方案 `BMAD-企业知识库RAG项目方案.md`，并按 `bmad-architecture/references/reviewer-gate.md` 的 good-spine checklist 检查。
- **脊柱未修改。** 本次未运行实现或测试。

## 机械检查

BMAD spine linter 的直接 Python 调用通过：`ok=true`、0 条发现（无占位符、重复/非递增 AD ID、缺少 Binds/Prevents/Rule 或无版本 Stack 行）。`uv run` 因为无法访问用户目录下的 uv cache 权限失败；改为直接运行同一只读脚本后完成检查。

## 主要发现

### 高优先级

#### H1 — Stack 表中多个锁定版本在方案日期前已被上游更新

- **位置：** 脊柱 `ARCHITECTURE-SPINE.md:97-111`；方案版本依据 `SOLUTION-DESIGN.md:190-202`。
- **证据：** 版本表列出 Python 3.14.2、SQLAlchemy 2.0.52、Node.js 24.13.0 和 TypeScript 6.0.2。官方来源显示 Python 3.14.7（2026-08-05）、SQLAlchemy 2.0.54（2026-09-15）、Node.js 24.21.0 LTS（2026-09-09）及 TypeScript 6.0.3 已发布；TypeScript 7.0.2 也已列为最新版本。参见 [Python 版本目录](https://www.python.org/doc/versions/)、[SQLAlchemy Releases](https://github.com/sqlalchemy/sqlalchemy/releases)、[Node.js Releases](https://nodejs.org/en/blog)、[TypeScript Releases](https://github.com/microsoft/TypeScript/releases)。其他代表性条目如 FastAPI 0.141.1、Vue 3.5.43 和 PostgreSQL 18.6 在抽查的上游资料中与日期相符。
- **影响：** “当前稳定版本”声明与精确版本表不一致；读者无法判断这些是有意的兼容性选择、锁文件目标，还是过期快照。SQLite 3.50.4 被作为本地架构版本固定，也把随 Python 构建而来的运行时细节误写成普遍要求。
- **处置：** **实现前修订。** 按兼容性与支持周期重新核对版本，随后在依赖文件中锁定确切版本并记录验证日期；不要仅为追逐最新 major 而升级。将 SQLite 描述为运行时能力/最低要求，实际值由本机运行时核验，不作为跨开发环境的硬架构版本。

### 中优先级

#### M1 — 稳定 Stage B 端口没有完整进入架构脊柱与伴随方案

- **位置：** 脊柱 `AD-4`、`AD-7`、Capability Map（`ARCHITECTURE-SPINE.md:56-78, 150-161`）；源方案接口清单（`BMAD-企业知识库RAG项目方案.md:73-84`）；方案 `SOLUTION-DESIGN.md:48-52`。
- **差异：** 源方案将 `DocumentParser`、`OCRProvider`、`Chunker`、`EmbeddingProvider`、`VectorStore`、`KeywordRetriever`、`KnowledgeRetriever` 和 `AnswerProvider` 列为必需接口，并要求真实 Provider 沿相同契约替换 mock。伴随方案与脊柱只明确了通用 ports、Parser、`KnowledgeRetriever`、`AnswerProvider` 等部分；OCR、切分、Embedding、向量存储和关键词检索的接口归属/关系未在决策中固定。算法和后端选择（Milvus vs pgvector、BM25/RRF）应当延后，接口边界可以先稳定。
- **影响：** “给后续真实 RAG 集成留稳定接入点”尚未覆盖源方案承诺的所有模块；Stage B 实施者可能各自决定 OCR/切分/向量职责和 Evidence 转换边界，损害 Provider 可替换性。
- **处置：** **讨论并修订。** 在脊柱或其明确引用的架构文档中登记上述端口、所有权和跨端口流向；把向量引擎、检索算法和是否在 Stage A 提供 mock 实现明确留在 Deferred。若这些接口并非 Stage A/Stage B 稳定性要求，则应同步收窄源方案的“必需接口”承诺。

#### M2 — AD-8 的“版本化迁移”与首启建表表述未收敛为单一操作规则

- **位置：** `AD-8`（`ARCHITECTURE-SPINE.md:80-84`）；`SOLUTION-DESIGN.md:44, 146-157, 175`。
- **差异：** 脊柱要求 SQLite 与 PostgreSQL 使用“版本化 schema migrations”；方案同时说“第一次启动时创建表结构”，但未说明这是执行迁移，还是 ORM `create_all`。方案只把 PostgreSQL 首次运行的一致性验证列为风险处理。配置入口、迁移执行者/时机、失败时服务是否启动也未记为约束。
- **影响：** SQLite 与 PostgreSQL 可能在启动路径分叉，进而违背 AD-8 要保证的同一 schema 合约；不同实现者也可能引入无法升级的隐式建表流程。
- **处置：** **修订。** 决定并写清唯一的迁移入口（例如本地与 Compose 启动都运行同一迁移机制，或由显式命令迁移后再启动）；把“第一次启动创建表”明确等同于运行迁移，或删除该表述。确认 DB URL/模式通过同一配置边界切换。

#### M3 — AD-2 描述了生成契约，却没有阻止手写类型漂移的执行门禁

- **位置：** `AD-2`（`ARCHITECTURE-SPINE.md:44-48`）；`SOLUTION-DESIGN.md:92-94`。
- **差异：** OpenAPI 为事实源、前端类型由 schema 生成已定为 Rule，但没有生成物位置、生成命令/版本或检查生成结果是否已提交且最新的约束。
- **影响：** 工程实践仍可以提交手写或过期 TS 类型，AD-2 所防止的前后端 contract drift 不能稳定复现为失败信号。
- **处置：** **修订。** 指定前端生成类型目录与唯一生成脚本，并由构建/CI 检查重新生成后无 diff，或使用等效的 contract compatibility 检查。

#### M4 — Stage B 的质量评测门槛没有进 Deferred 或能力/验收地图

- **位置：** 源方案 `BMAD-企业知识库RAG项目方案.md:124-128`；脊柱 `## Deferred`（`ARCHITECTURE-SPINE.md:163` 起）。
- **差异：** 源方案把至少 30 条黄金问题集、Recall@5、引用有效率和无答案识别作为真实内容接入后的质量评估；脊柱 Deferred 有向量/混合检索选型，但没有评测集与质量验收这一后续活动。
- **影响：** 将来可以完成真实 Provider 接入却缺少评测触发和引用正确性度量，仍然声称功能已就绪。当前不需要 Stage A 声称检索指标。
- **处置：** **加到 Deferred。** 明确以真实语料/Provider 接入为触发点，采用源方案的评测维度与建议初值并允许按语料校准；不得把建议 Recall@5 目标误作 Stage A 验收项。

### 低优先级 / 评审尾项

- **L1（运维边界）：** Stage A 的本机 SQLite、Compose PostgreSQL 和上传卷已有决定；`SOLUTION-DESIGN.md:153-157` 还要求 `.env.example`、健康检查和持久化。脊柱只画了服务拓扑，没有定环境配置/启动入口、API 健康/就绪检查、上传大小/扩展名配置来源。建议在脊柱明确最小运行约定，或指向方案中的规范章节。生产观测、外部存储、共享部署认证均已有合适的 Deferred 触发条件。
- **L2（AD-3 完整性）：** 层级和可追溯约束清楚且能由领域校验实现；如希望“existing Chunk ID”在并发/持久化边界上也不可破坏，实施约束应落成外键或等价验证规则。不是本次通过的阻塞项。

## AD 逐项可执行性审查

| 决策 | 是否可执行 | 审查意见 |
| --- | --- | --- |
| AD-1 单应用与向内依赖 | 是 | 路由→用例→领域/端口的依赖方向清楚，组合根选适配器；Capability Map 也能对应到组件边界。 |
| AD-2 唯一 API 契约 | 部分 | FastAPI/Pydantic→OpenAPI→前端生成类型方向明确；缺生成物和 drift 检查（M3）。错误对象字段也已具体列出。 |
| AD-3 来源层级与证据身份 | 是 | 关系与定位元数据明确，可在应用层和持久化层校验；建议实现时将引用关系落到 FK/等价校验（L2）。 |
| AD-4 每个结果显式 mock/live | 是 | 值域、Stage A 限制、服务端启用 live 的条件和 UI 显示位置都有可观察的执行规则。 |
| AD-5 Run 与安全事件流 | 是 | run_id、序号、字段、先持久化后发布、SSE 与详情同源及禁止暴露推理内容均可验证；实施时需用唯一约束/事件 schema 落实。 |
| AD-6 元数据/文件分责 | 是 | Repository、FileStore、storage_key 与未来对象存储适配器的所有权清楚。 |
| AD-7 Stage A 不依赖外部 RAG 基础设施 | 是 | Parser/Retriever/Answer/ProviderStatus 使用 fixture 的界限及禁止依赖明确；与 Stage A 本地演示范围一致。 |
| AD-8 SQLite/Compose 共享仓储合约 | 部分 | ORM/repository、方言规则和 DB 目标已清楚；迁移执行/首启建表语义需收敛（M2），Stack 版本也需更新（H1）。 |

## Checklist 汇总

- **范围适配：** 符合 Stage A 本地 demo workbench 与 modular-monolith 的项目高度；没有把源方案中的 OCR、向量库或真实质量指标偷偷纳入 Stage A。
- **源需求覆盖：** Stage A 七类工作台能力（知识库/文档、Chunk、检索、问答引用、运行追踪、Provider）在能力映射中均有归属，核心 API/SSE/证据规则大体覆盖。阶段 B 的适配器和质量评测约束不足，见 M1/M4。
- **AD 规则：** 8 条均有 Binds/Prevents/Rule，lint 通过。AD-1、AD-3 至 AD-7 的规则均可落地；AD-2、AD-8 需补执行机制或消歧。
- **Deferred：** 当前列出的不确定性多有清晰复核条件；身份/多租户在共享部署前复核、异步任务在处理超过请求生命周期时复核的触发边界合理。增加质量评估项（M4）。
- **命名技术：** 精确版本已填，但代表性依赖过时，且 companion 以“实现开始时锁定”为准，与脊柱精确 pin 有落差（H1）。
- **代码库棕地一致性：** 本次输入仅包含方案文件，没有看到既有代码库或上级脊柱，无法确认是否 ratify 现存实现/继承决策；本评审未发现自相矛盾的继承项。
- **运行/环境边界：** local/Compose、DB/文件所有权和 Stage A 无外部 RAG 服务的边界不错；迁移/启动规则需补齐，健康和配置规范偏弱（M2/L1）。

## 建议通过条件

先修 H1；再定稿 M1（稳定端口范围）、M2（统一迁移/首启策略）和 M3（生成类型 drift 检查）。M4 与 L1 应进入相应 Deferred/运行约定章节后再做实现交接。以上均属于文档层修订，本评审没有更改架构脊柱。
