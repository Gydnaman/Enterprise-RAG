---
title: '企业知识库 RAG Agent 工作台 Stage A'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'NO_VCS'
context:
  - docs/architecture/architecture-enterprise-rag-workbench-2026-09-23/SOLUTION-DESIGN.md
  - docs/architecture/architecture-enterprise-rag-workbench-2026-09-23/ARCHITECTURE-SPINE.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 需要一个可独立运行、适合作品集演示的企业知识库工作台；当前没有可用于证明真实解析和 RAG 质量的授权语料。

**Approach:** 在同一产品中交付知识库、文档、Chunk、检索、问答、Run 追踪和 Provider 状态七类页面，以及由统一 FastAPI/OpenAPI 契约驱动的 Vue 前端。用只读 fixture 演示可追溯证据，用标明 DEMO/MOCK 的流程展示运行状态；用户上传只安全保存，不解析或参与检索。

## Boundaries & Constraints

**Always:** 采用已批准技术方案中的 Vue 3.5/TypeScript 6/Vite 8、Python 3.13/FastAPI/Pydantic/LangGraph、SQLAlchemy/Alembic 和 SQLite/PostgreSQL。模块化单体分层；OpenAPI 是 Web 类型事实源；统一 Problem、持久 RunEvent 与可续传 SSE。用户文件经过大小、扩展名、签名校验并使用服务端 opaque key；文档和 Run 的状态需在页面可观察。附件只提供蓝色工作台视觉方向。

**Never:** 不连接真实 LLM/OCR/向量库，不从用户文件生成 Section/Chunk/Evidence，不将模拟轨迹或分数描述成真实解析或检索效果；不在前端保存密钥；不加入生产级队列、多租户认证或未批准的外部服务。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| fixture retrieval | ready fixture + query | 持久化 retrieval Run，返回有 revision/Chunk 身份的 DEMO Evidence | 空结果显示资料不足 |
| uploaded document | 合法上传文件 | 保存为 uploaded_unprocessed；Chunk 为空且不可检索 | 不匹配签名或超限时返回 Problem，清理临时文件 |
| upload recovery | upload_pending + same idempotency key | digest 匹配则 finalize；成功返回 201，仍处理中 202 | 暂时无法 finalize 返回 503 并保留恢复信息 |
| chat reconnect | active/finished answer Run + Last-Event-ID | 从已确认序号后补发事件，终态后结束 | 非法或超前 cursor 返回 invalid_sse_cursor |

</frozen-after-approval>

## Code Map

- `docs/architecture/architecture-enterprise-rag-workbench-2026-09-23/SOLUTION-DESIGN.md` — 已评审的 API、状态机、上传恢复、UI 流程和栈；实现必须遵循。
- `docs/architecture/architecture-enterprise-rag-workbench-2026-09-23/ARCHITECTURE-SPINE.md` — 分层、DTO、存储、fixture 与部署不变量。
- `apps/api/src/rag_workbench/`、`apps/web/src/` — Stage A API 与 UI 实现。
- `docs/specs/` — 规格归档目录；本 spec 是首个实现基线，项目此前没有 PRD 或 epic。
- 历史说明：最初的实现位于无 Git 元数据的 `work` 目录；此文档后来归档到独立 Git 发布仓库。

## Tasks & Acceptance

**Execution:**
- [x] `apps/api/pyproject.toml`、`apps/api/src/rag_workbench/`、`apps/api/alembic/` — 建立领域/应用/适配器/API 分层、显式迁移、fixture seed、上传 FileStore、Run dispatcher 与 Stage A 路由。
- [x] `docs/api/openapi.json`、`apps/web/src/api/generated/types.gen.ts` — 生成并锁定 API 契约类型；提供 drift 检查命令。
- [x] `apps/web/package.json`、`apps/web/src/` — 实现七类页面、蓝白工作台视觉、可访问表单、加载/空/错误状态、SSE 恢复和 DEMO/MOCK 标记。
- [x] `compose.yaml`、`.env.example`、`.gitignore`、`README.md` — 配置 SQLite 本地运行及 loopback-only PostgreSQL Compose、迁移、健康检查和演示步骤。

**Acceptance Criteria:**
- Given 空数据库，when 启动本地 API 与 Web，then Alembic 初始化 SQLite、Demo KB/fixture 可见，七类页面可从同一 API 工作。
- Given ready fixture，when 检索并提问，then Evidence/Citation 回指同一 revision/Chunk；无 Evidence 时回答资料不足且不造引用。
- Given 合法用户文件，when 上传并运行 demo_trace/retry，then 文件只保存在 uploaded_unprocessed，Run 可追踪，Chunk 与检索结果不含该文件。
- Given 同 key 重放或上传恢复，when 请求重复/服务重启，then 返回一致资源，pending 上传先恢复，终态 Run 不接受迟到写入。
- Given Run SSE 断开，when 使用 Last-Event-ID 重连，then 不漏不重地补发持久事件；非法 cursor 返回统一 Problem。
- Given Compose 启动，when PostgreSQL 健康且迁移成功，then Web/API 仅发布到 loopback，API readiness 确认 schema。
- Given 任一展示结果，then 清楚标为 DEMO/MOCK；浏览器和错误 DTO 不泄漏本地路径、密钥或异常栈。

## Implementation Notes

- 已交付 Stage A 模块化单体：FastAPI/Pydantic、SQLAlchemy/Alembic、LangGraph mock workflow、SQLite 本地库与 loopback-only PostgreSQL Compose，以及 Vue 3/TypeScript 工作台七类页面。
- Demo Fixture 提供可回溯的 Revision/Section/Chunk/Evidence/Citation；用户上传经过大小、扩展名、签名校验后只安全保存为 `uploaded_unprocessed`，不会解析或参与检索。
- Run 与事件持久化，SSE 支持恢复；上传失败保留 pending 恢复状态。OpenAPI 是前端类型事实源，幂等键在同一失败操作重试期间持久化。
- 安装官方 BMAD Method v6.12.0；实施盲审发现的 11 项 patch 已修复并复核，另 1 项 API 类型 drift 结论以当前通过的 `pnpm api:check` 证伪。无 bad_spec/intent_gap/defer 项。
- 历史说明：编写本 spec 时，原始 `work` 实施目录没有 Git 元数据，因此没有在该目录创建分支、提交或 PR；项目后续通过单独的发布仓库完成 Git 提交与推送。未运行测试套件，也未启动 API/Web 服务或 Compose；因此浏览器演示路径、SSE 断线场景和 PostgreSQL Compose 尚未手工演练。

## Spec Change Log

## Review Triage Log

- medium / patch — `README.md` 本地启动说明要求复制并修改 `.env`，但 `uv run` 未指定 `--env-file`，而 `config.py` 只读进程环境变量；本地运行会忽略这些覆盖项。已验证当前 uv 支持 `--env-file`，修复为本地命令显式加载文件。
- medium / patch — Alembic 基线 `0001_stage_a.py` 在 upgrade/downgrade 中动态调用当前 `Base.metadata.create_all/drop_all`；后续 ORM 变更会改变旧 revision 的效果，使新数据库预先创建未来列、后续迁移再添加时冲突。按已批准方案的单一、可重复 Alembic revision 约束，改成显式 revision 操作。
- medium / patch — 上传路由以 FastAPI `UploadFile = File(...)` 接收请求，handler 才调用有大小上限的 staging；multipart 解析阶段可先将超限 body 写到 Starlette 临时文件。新增请求体前置上限，阻止解析阶段接受超限上传。
- medium / patch — `run_answer` 只用 `evidence[0]` 生成答案，却为 `evidence[:3]` 持久化 Citation；较低排序 Evidence 没参与答案生成却被展示为答案来源。Citation 限定到实际用于答案的首条 Evidence。
- false — Run 详情没有跟随 `nextAfterSequence` 翻页，但 Stage A 的固定检索 Fixture snippet 截断为 600 字符，Mock answer 最多产生 8 个 delta，连同阶段/引用事件仍低于默认 50 条；现有可达 workflow 不会出现审查意见所说的长答案截断。
- medium / patch — 文档列表 API 默认返回 50 条，`DocumentsPage` 只读取 `items` 且无后续页入口；用户上传超过 50 个文件后其余文档不可见。增加分页加载。
- medium / patch — `/runs` 页面只读取默认第一页，操作超过 50 次后较早运行记录不可见。首页明确展示“最近运行”五条并提供“查看全部”链接，首页部分不构成缺陷；为 `/runs` 增加分页加载。
- low / patch — 知识库切换 watcher 未捕获 `loadDocuments()` 失败，网络错误会留下旧筛选项且不在页面显示错误。此处可用直接错误处理修复，不需额外复杂状态。
- medium / patch — 上传、检索、处理和问答客户端每次提交都创建新 Idempotency-Key；请求已提交但响应超时后用户重试，会被服务端当成新操作。保留失败操作的 key，成功或输入变更后再换新 key。
- medium / patch — `/runs?knowledgeBaseId=...` 先取全表，在 Python 逐行按文档归属过滤后才分页；上传/demo trace 还逐行查询文档，记录增长时数据库读取和查询次数不受 pageSize 限制。改为在数据库过滤并分页。
- false — answer graph 调用 `MockAnswerProvider` 时传入空历史，但当前 Mock provider 的实现完全不读取 history，且 Stage A 已批准范围未承诺多轮语义；没有展示出当前实现中可由传入历史避免的用户可见结果差异。
- high / patch — `apps/web/package.json` 单独声明 `@hey-api/typescript@0.99.0`，pnpm registry 返回 404，导致安装依赖失败；Hey API 的 TypeScript 插件由 `@hey-api/openapi-ts` 包提供。移除不存在的独立依赖，保留生成器插件配置。
- medium / patch — `ChatPage.vue` 恢复含活动答案的会话时，页面加载了持久化的部分答案，而新建 EventSource 未带 Last-Event-ID 会从首个事件重放并再次追加文本/Citation。重放前清空活动 assistant 的文本与 Citation，让持久事件重新构建当前输出。
- medium / patch — 上传首次 finalize 遇到 `OSError` 时原实现把 idempotency、Document、Run 都写成终态失败；启动恢复只处理 pending，同 key 重试也直接返回失败。保留 pending/running 状态并让恢复流程在临时存储错误时跳过该条，允许同 key 重试或后续启动恢复。
- false — Blind Hunter 关于 OpenAPI 生成类型名称与已提交类型不一致的判断针对旧生成结果；重新运行 `pnpm api:generate` 后，`pnpm api:check` 对临时生成文件与提交文件逐字节比较并通过，当前不存在该 drift。
- medium / patch — `check-api.mjs` 在 `try/finally` 内调用 `process.exit()` 会跳过 finally 清理并遗留 `.openapi-check-*`。改为设置 `process.exitCode`，由 finally 删除当前输出，并在 `.gitignore` 忽略该临时目录模式。
- medium / patch — 上传、处理和重试的 Idempotency-Key 参数默认 `""`，FastAPI 因而将契约标成可选，但 handler 会拒绝缺失值。移除空字符串默认并重新导出 OpenAPI，使头字段必填。
- medium / patch — Retrieval 页切换知识库时只清空筛选文档，仍显示上个知识库的 Evidence/Run。切换时清空结果状态。
- medium / patch — Retrieval 搜索请求完成后无条件覆盖页面，知识库切换期间的旧请求会把旧 Evidence 写到新知识库。使用请求 generation 与目标知识库校验，丢弃旧结果、错误和 finally 更新。
- medium / patch — Documents 页只读取最近 100 条 Run，较早 Demo Trace 消失后会再次提供已被服务端拒绝的处理操作。复用 `/runs` 的知识库与类型 SQL 过滤，分页载入该知识库全部 Demo Trace。
- medium / patch — RunDetail 路由切换或新 Run 加载失败时，旧快照仍留在页面状态。加载开始时清空 route-bound 状态，并以 generation/id 校验丢弃过期响应。
- medium / patch — Documents 页切换知识库请求失败时会把旧知识库、文档显示在新路由下。加载前清空状态，并忽略旧路由的响应、错误和 finally 更新。
- medium / patch — IdempotencyKeyManager 与 File identity 只在组件内存中；刷新后无法用相同文件/请求键恢复不确定的上传。按知识库与文件 SHA-256 构造稳定身份，并把 pending key 存入 localStorage，操作成功后清理。
- medium / patch — `_queue_demo_trace` 读取所有 demo_trace Run 后在 Python 中按文档筛选。改为用 `demo_document_id` 与 `kind` 在数据库中筛选，复用唯一复合索引并只加载该文档的 attempts。

## Verification

**Commands:**
- `pnpm api:check` — passed; generated API types match OpenAPI.
- `pnpm typecheck` — passed.
- `pnpm build` — passed; Vite production build completed.
- `uv --cache-dir .uv-cache run --project apps/api --locked ruff check apps/api/src` — passed.
- `uv --cache-dir .uv-cache run --project apps/api --locked python -m compileall -q apps/api/src` — passed.
- `uv --cache-dir .uv-cache run --project apps/api --locked alembic -c apps/api/alembic.ini upgrade head` — passed on fresh SQLite; `current` reports `0001_stage_a (head)`.
- `uv --cache-dir .uv-cache lock --project apps/api --check` — passed.
- 未运行测试套件。

**Manual checks:**
- 未手动启动应用；README 演示流程与 PostgreSQL Compose 留待后续浏览器演练。

