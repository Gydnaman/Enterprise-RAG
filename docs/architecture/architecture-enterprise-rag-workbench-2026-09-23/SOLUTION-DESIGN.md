# 企业知识库 RAG Agent 工作台：技术方案

> 状态：BMAD 技术方案终稿（评审通过，Stage A 可实施）  
> 日期：2026-09-24  
> 目的：为阶段 A 的实现确定模块边界、接口契约、运行方式和验收条件；为阶段 B 的真实 RAG 接入保留稳定端口。

## 决策摘要

本项目按模块化单体实施：Vue 工作台调用 FastAPI 的版本化 API；应用用例通过领域类型和端口连接 SQLAlchemy Repository、LocalFileStore 与 fixture/mock adapters。阶段 A 使用 LangGraph 编排确定性 mock 问答流程，数据库支持本机 SQLite 与 PostgreSQL Compose 两种运行方式。

| 选择 | 决策 |
| --- | --- |
| Web | Vue 3.5.43、TypeScript 6.0.3、Vite 8.3.0、Node.js 24.21.0 LTS |
| API/流程 | Python 3.13.15、FastAPI 0.141.1、Pydantic 2.13.5、LangGraph 1.2.12 |
| 数据 | SQLAlchemy 2.0.54、Alembic 1.20.0、psycopg[binary] 3.3.6；本机 SQLite、Compose PostgreSQL 18.6 |
| API 类型 | OpenAPI 为事实源；@hey-api/openapi-ts 0.99.0 生成 Web 类型 |
| Stage A provider | 只允许启动时校验过的 mock profile；不接外部模型、OCR、向量库或密钥 |
| 用户上传 | 只做类型/大小/签名安全校验并保存文件与元数据，不提取文本、不生成 Section/Chunk、不参与检索；fixture 文档提供可追溯的 Chunk 与 Evidence 演示 |
| 阶段 B | 通过稳定端口接入 Parser/OCR/Chunker/Embedding/VectorStore/KeywordRetriever/AnswerProvider，不改 Web API 契约 |

选 Python 3.13.15 是为了与 LangGraph 1.2.12 已列出的 Python classifier 范围一致；虽然 Python 3.14.7 更新，但 LangGraph 的该版本没有声明 3.14 classifier。TypeScript 选 6.0.3 以匹配 Vue/Volar 目前依赖的稳定 TypeScript API；代码生成器改用不要求旧版 TypeScript peer 的 @hey-api/openapi-ts 0.99.0。SQLite 版本由 Python 构建提供，运行时检测而不单独 pin。

## 1. 范围、目标和来源边界

源方案的当前目标是求职作品集与学习演示：先搭项目骨架、页面、API、领域对象、fixture/mock 和可替换接口；真实知识内容、解析、检索链路及质量评估后续接入。阶段 A 不声称真实解析完成、不宣称 RAG 准确率，也不输出私有模型推理。

源文件中关于安装器、技能、工具和执行顺序的内容是方案材料。本轮实际授权是阅读该方案、在线调研、先形成 BMAD 技术方案、评审通过后开始实现。没有因源文件中的命令文字自动运行安装命令，也不会把其中的流程建议当成已执行事实。

阶段 A 包含知识库、文档/上传、Section/Chunk 观察、检索调试、带引用的聊天、Run 追踪、Provider 状态七类页面和相应 API。阶段 B 再接真实语料与 RAG pipeline。多租户 SSO、复杂权限继承、生产级异步调度、知识图谱与大规模语料优化不在当前范围。

## 2. 在线调研：开源项目和可借鉴架构

| 项目 | 官方仓库/文档呈现的架构 | 本方案借鉴点 | 当前不照搬的部分 |
| --- | --- | --- | --- |
| [MaxKB](https://github.com/1Panel-dev/MaxKB) | Vue、Python/Django、LangChain、PostgreSQL/pgvector；企业知识库、文档处理和 Agent 工作流。 | 工作台交互形态验证 Vue + Python API + PostgreSQL 的组合；文档处理是可观察流程。 | 本项目沿用源方案的 FastAPI；只借鉴架构思想，不复制其 GPLv3 实现。 |
| [FastGPT](https://github.com/labring/FastGPT) | Dataset → Collection → data entry；PostgreSQL/pgvector 存向量，检索可组合向量、全文、查询改写、RRF 与重排。 | 证据必须带来源身份；页面只消费统一 Evidence 契约；混合检索由 KnowledgeRetriever 负责。 | 不在没有真实语料和负载时引入 MongoDB、pgvector 或复杂检索链。 |
| [RAGFlow](https://github.com/infiniflow/ragflow) | 强调解析/分块可视化、引用溯源和融合检索；完整本地依赖较重，涉及 Elasticsearch/Infinity、MySQL、Redis、MinIO。 | 解析状态、Chunk 预览、来源定位和运行轨迹应当是一等能力。 | 阶段 A 不启动完整 RAG 基础设施。 |
| [Dify API 开发说明](https://github.com/langgenius/dify/blob/main/api/README.md) | API、Web 与 worker 分进程；开发依赖包括 PostgreSQL、Redis、Weaviate。 | 真实处理跨请求生命周期后，应把持久异步工作与 Web 请求分开。 | Stage A mock 流不需要额外 worker、Redis 或 Weaviate。 |

**调研结论：**采用与 MaxKB 相近的 Vue/Python/PostgreSQL 工作台方向，以 FastGPT 的数据集与证据分层作为检索边界参考，并用 RAGFlow、Dify 校准后续处理复杂度。阶段 A 收敛为单应用模块化单体；后续复杂度由真实语料、部署负载和质量评测触发。

## 3. 架构和技术选择

### 3.1 Web 与 API

Web 使用 Vue 3.5.43 + TypeScript 6.0.3 + Vite 8.3.0，运行时 Node.js 24.21.0 LTS。API 使用 Python 3.13.15、FastAPI 0.141.1 和 Pydantic 2.13.5。FastAPI/Pydantic DTO 生成 OpenAPI；Web 从同一 OpenAPI 文件生成 TypeScript 类型。浏览器不包含模型 SDK、Provider 密钥或检索编排逻辑。

LangGraph 1.2.12 是阶段 A 问答流程的固定编排器。它只组织确定性 mock 节点，并将安全的阶段摘要和答案增量映射到 RunEvent；Domain、Repository 与公开 API 都不依赖 LangGraph state。阶段 A 不启用 checkpoint，Run/RunEvent 由本应用持久化。此为已选决策，不留到编码时再切换。

### 3.2 元数据、迁移和文件

SQLAlchemy 2.0.54 提供统一 Repository；Alembic 1.20.0 是唯一 schema 迁移机制。本机无 Docker 时使用 SQLite；Compose 使用 PostgreSQL 18.6 与 psycopg[binary] 3.3.6。PostgreSQL URL 使用 `postgresql+psycopg://` 驱动标识；数据库连接由同一个 DATABASE_URL 边界配置，所有迁移按相同 revision history 执行。SQLite 每次连接都启用外键，Stage A 避免循环外键及数据库专有 SQL。

文件字节由 LocalFileStore 放在 data/uploads/；数据库只保存文档、revision、文件大小/类型、状态和不透明 storage_key。上传文件路径永远由服务端生成，不采用用户文件名作为路径。Stage B 可加对象存储适配器而不改 Document API。

### 3.3 检索、回答和 Stage B 稳定端口

阶段 A 的 MockKnowledgeRetriever 从只读 fixture 返回 Evidence；MockAnswerProvider 只基于这些 Evidence 生成演示回答。每个 provider 结果带 mode=mock，展示回答、证据或分数的界面持续显示“DEMO / MOCK”。无 Evidence 时系统输出固定的资料不足答复，不编造引用。

以下端口进入架构基线。Stage A 实现 FileStore、KnowledgeRetriever、AnswerProvider 和运行调度；Parser 等接口先确定边界，不解析用户上传。Stage B 的真实适配器沿用相同输入/输出契约：

| Port | 所属责任与阶段 B 流向 | Stage A |
| --- | --- | --- |
| FileStore.open(storage_key) → BinaryIO | 按不透明 key 提供受控只读流，不向调用方暴露本地路径。 | LocalFileStore 读取已保存的用户上传。 |
| DocumentParser.parse(stream, revision_metadata) → ParsedDocument | 编排文件类型识别、原生提取或 OCR 路径；通过 FileStore 流读取，不直接访问文件系统。 | 只针对内置 fixture 输入；不解析任意用户上传。 |
| OCRProvider.extract(file) → OCRResult | 对扫描件/图像提供页级文本与定位，交由 Parser 组合。 | 未实现。 |
| Chunker.split(parsed_document, policy) → Chunk[] | 在保留页码、标题路径和顺序的前提下切分；输出领域 Chunk。 | Fixture 提供固定 Sections/Chunks。 |
| EmbeddingProvider.embed(texts) → Vector[] | 将文本向量化，模型信息由 adapter 管理。 | 未实现。 |
| VectorStore.upsert/delete/search(...) | 按 revision 管理向量索引；返回原始命中身份和分数，不直接决定 UI DTO。 | 未实现；不引入 Milvus/pgvector。 |
| KeywordRetriever.search(query, filters, k) → Evidence[] | 提供关键词/全文候选并保留 Chunk 来源身份。 | 未实现。 |
| KnowledgeRetriever.retrieve(query, filters, k) → Evidence[] | 对向量与关键词候选做融合（可选 BM25/RRF/重排），生成规范 Evidence。 | Mock 从 fixture 返回固定 Evidence。 |
| AnswerProvider.stream(question, evidence, history, cancellation) → AsyncIterator[AnswerEvent] | 只消费规范 Evidence；异步逐条输出答案增量与被引用来源，可响应应用关闭取消信号。 | MockAnswerProvider 返回确定性答案和 citations。 |

依赖方向为 API route → application use case → Domain/ports → adapters。Parser 编排 OCRProvider 与 Chunker；索引 use case 调用 EmbeddingProvider、VectorStore；KnowledgeRetriever 组合向量与关键词命中；AnswerProvider 只接收 Evidence。模型 SDK、数据库和框架不得反向进入 Domain。向量引擎、嵌入模型、BM25/RRF 参数及重排器在有真实语料后，通过质量评测选择。

### 3.4 部署拓扑

~~~mermaid
flowchart LR
  Browser[Vue workbench] -->|REST + SSE /api/v1| API[FastAPI modular monolith]
  API --> UseCases[Application use cases]
  UseCases --> Domain[Domain rules]
  UseCases --> Ports[Repository / FileStore / RAG ports]
  Ports --> Mock[Fixture adapters]
  Ports --> SQL[SQLAlchemy repositories]
  SQL --> DB[(SQLite local or PostgreSQL Compose)]
  Ports --> Files[LocalFileStore]
  Files --> Disk[(Uploads volume)]
  Migrate[One-shot Alembic migration] --> DB
  API -. starts after migration succeeds .-> Migrate
~~~

本机开发中 Vite 和 API 使用不同端口，Vite dev server 将 /api/v1 代理到 API，SSE 不缓冲。Compose 演示模式中，浏览器读取显式 VITE_API_BASE_URL（默认 http://localhost:8000/api/v1），API 只允许 .env 中配置的确切 Web 来源；不依赖容器内 hostname 被宿主浏览器解析。Compose 只用于本机演示，不能当成生产多实例拓扑。

## 4. 领域对象、身份和所有权

| 对象 | 责任与关键关系 |
| --- | --- |
| KnowledgeBase | 知识集合；拥有 Document；使用稳定 UUID。 |
| Document | 文件显示元数据、知识库归属、fixture 标记和当前显示状态；每次新的上传请求创建一个独立 Document 及其初始 Revision；不直接存文件内容。 |
| DocumentRevision | 不可变的输入版本，包含 revision number、storage key 或 fixture key、处理状态和内容指纹。重处理生成新 revision；只在新版本成功后切为 current。 |
| Section | 属于一个 revision；保留顺序、页码范围和标题路径。 |
| Chunk | 属于一个 Section；保留文本、顺序、字符/页定位及稳定 ID。 |
| Evidence | 单次检索对 Chunk 的投影，包含 revision_id、chunk_id、分数、命中摘要和 mode。 |
| Citation | 绑定一个 Evidence 的 revision 和 Chunk 身份；不只保存可能变化的文档名称或 URL。 |
| Conversation / Message | 会话固定一个 KnowledgeBase；每条消息有角色、顺序和状态。回答消息关联产生它的 Run 与 citations。 |
| Run | 一次 upload、demo_trace、retrieval 或 answer 操作的身份、类型、状态、幂等键和时间。Run kind 枚举为 `upload`, `demo_trace`, `retrieval`, `answer`。 |
| RunEvent | 属于 Run 的有序安全事件；以 (run_id, sequence) 唯一标识。 |
| ProviderStatus | 当前 immutable adapter profile 的服务端状态投影，不含凭据或内部异常文本。 |

ID 使用小写 UUID 字符串；内置演示源使用 fixture_ 稳定 ID，不和用户创建的 UUID 混用。Fixture 文件在仓库中只读；启动 seed 按固定 key 幂等插入，不能覆盖同 key 的用户数据。Stage A 不提供修改或删除 fixture 的 API。用户创建的 KnowledgeBase/Document 总是独立记录。

Section/Chunk 属于 DocumentRevision，不是可变的 Document head。Evidence 与 Citation 同时引用 revision 和 Chunk；历史 Run 仍可读到原始来源。未来重处理新增 revision，失败时保留旧的 current revision；硬删除和跨版本迁移不在 Stage A 范围。数据库约束必须避免循环外键，保留父级校验和 (revision_id, chunk_id) 唯一性。

## 5. API、状态机与流式事件契约

### 5.1 JSON 与 DTO 约定

- 基础路径统一为 /api/v1。Python 属性用 snake_case；线上的 JSON key 用共享 alias generator 输出 camelCase，缩写按 knowledgeBaseId 形式处理；请求校验与响应序列化都使用 aliases。
- DTO 名称和枚举集中定义：KnowledgeBase、Document、DocumentRevision、Section、Chunk、Evidence、Citation、Conversation、Message、Run、RunEvent、ProviderStatus、分页和 Problem DTO。字段在 OpenAPI 中唯一声明，禁止 endpoint 自定义同义字段。
- 领域 ID 为字符串，时间为带 Z 的 UTC ISO 8601。枚举值一律 lower_snake_case。响应 DTO 表中除以 `?` 标记为可空的字段外，所有字段必需且非 null；可空字段也必需并以 JSON null 序列化。请求 DTO 独立定义；请求字段可以标为 optional，省略与显式 null 只有在该请求 schema 明确允许时才等价。当前阶段没有 PATCH。
- 普通列表返回 {items, page, pageSize, total}；page 默认 1 且必须 ≥1，pageSize 默认 50 且为 1–100。RunEvent 使用 afterSequence 游标，不按时间翻页；event 页 limit 默认 50、最大 500。
- 生成源是 docs/api/openapi.json；生成文件为 apps/web/src/api/generated/types.gen.ts。pnpm api:generate 运行锁定在 package.json/pnpm-lock.yaml 的 @hey-api/openapi-ts 0.99.0，配置只启用 `@hey-api/typescript` 插件；pnpm api:check 重新生成到临时目录并在有 diff 时失败。API schema 更新必须连同生成类型一起提交。

主要响应 DTO 的公开字段固定如下；`storage_key`、本地路径、文件哈希原文和 provider 内部配置不进入浏览器 DTO。

| DTO | 字段与约束 |
| --- | --- |
| KnowledgeBase | `id, name, description?, createdAt, updatedAt`；name trim 后 1–120 字符；description 非 null 时 trim 后 1–2000 字符。 |
| Document / DocumentRevision | Document：`id, knowledgeBaseId, filename, mediaType, sizeBytes, isFixture, status, currentRevisionId, createdAt`；Revision：`id, documentId, revisionNumber, status, createdAt`。Document.status 与 Revision.status 为 `upload_pending`, `ready`, `uploaded_unprocessed`, `upload_failed`；filename 最多 255 UTF-8 bytes；storage key 只在服务端使用。 |
| DocumentDetail | `{document: Document, currentRevision: DocumentRevision, isRetrievable}`；currentRevision 必需且非 null，每个 Document 建立时同步创建初始 Revision。 |
| Section / Chunk | Section：`id, revisionId, title, order, pageStart?, pageEnd?, headingPath`；Chunk：`id, sectionId, order, text, pageStart?, pageEnd?, startOffset?, endOffset?`。无解析数据返回空 sections，不伪造 revision。 |
| Evidence / Citation | Evidence：`revisionId, chunkId, documentId, filename, page?, headingPath, snippet, score, rank, mode`；Citation：`revisionId, chunkId, page?, quote`。每条都可回查到该 KB 下真实存在的 ready fixture Chunk。 |
| Conversation / Message | Conversation：`id, knowledgeBaseId, createdAt`；Message：`id, conversationId, sequence, role, status, content, citations, runId?, createdAt`。role 为 `user`, `assistant`；Message.status 为 `queued`, `streaming`, `completed`, `failed`，user message 始终 completed；user message 的 runId 为 null，assistant message 的 runId 必需非 null；question trim 后 1–4000 字符，assistant content 最多 20,000 字符；citations 必需且可为空数组；每会话 sequence 从 1 递增。 |
| ConversationDetail | `{conversation: Conversation, messages: Message[], activeRunId?}`；activeRunId 在无进行中回答时为 null。 |
| Run / RunEvent | Run：`id, kind, status, mode, subject, createdAt, startedAt?, finishedAt?, resultStatus?, safeErrorCode?`；Event：`runId, sequence, eventType, phase, status, timestamp, payload`。Run.status 为 `queued`, `running`, `completed`, `failed`；kind 为 `upload`, `demo_trace`, `retrieval`, `answer`；`subject` 是带 kind 的来源 union：upload=`knowledgeBaseId,documentId,revisionId`；demo_trace=`documentId,revisionId,attemptNumber`；retrieval=`knowledgeBaseId`；answer=`knowledgeBaseId,conversationId,userMessageId,assistantMessageId`。mode 固定为 `mock`；sequence 从 1 开始；首个游标为 0。 |
| ProviderStatus | `provider, profile, mode, registered, selected, available, statusMessage?`；statusMessage 可空；不包含 credentials、环境变量值、SDK 原始错误。 |
| Page<T> / Problem | Page：`items, page, pageSize, total`；Problem：`type, title, status, detail, code, requestId, retryable, runId?`。Problem 的线上 requestId 对应内部 request_id；runId 在无关联 Run 时为 null。所有响应都带 `X-Request-ID` header；Problem body 也含 requestId。 |

主要请求 schema 独立于上述响应 DTO：`CreateKnowledgeBaseRequest={name:string, description?:string|null}`；`CreateConversationRequest={knowledgeBaseId:UUID}`；`SendMessageRequest={question:string(1–4000), topK?:integer(1–20)}`；`RetrievalDebugRequest={knowledgeBaseId:UUID, query:string(1–4000), documentIds?:UUID[], topK?:integer(1–20)}`。文件上传是 multipart request，不使用 JSON DTO；Idempotency-Key 是必填 header 的独立约束。

所有资源路由都先校验父级归属。`documentIds` 中任一文档不属于请求 KB、非 ready fixture 或 ID 不存在时，整次检索请求失败为 422；不会静默忽略非法过滤项。`question`、KB 名称/描述、分页页码、topK、游标和 limit 都在 DTO 层设上限。

### 5.2 Stage A 路由

| 方法和路径 | 请求 / 行为 | 响应 |
| --- | --- | --- |
| GET /knowledge-bases | 分页列表。 | Page<KnowledgeBase>。 |
| POST /knowledge-bases | {name, description?}；名称 trim 后非空且最多 120 字符；description 可省略、null 或 1–2000 字符非空文本。 | 201 KnowledgeBase。 |
| GET /knowledge-bases/{id}/documents | 分页文档列表，包含 upload_pending 与 upload_failed。 | Page<Document>。 |
| POST /knowledge-bases/{id}/documents | multipart file + Idempotency-Key；每个未重放的新 key 创建新 Document 和初始 Revision；只做类型/大小/签名校验，不提取文本。 | 新操作 finalize 后 201 `{document,revision,run}`。相同 key 的已完成重放为 201 并返回当前资源；pending replay 若仍在处理中为 202 pending DTO，若本次 replay 恢复 finalize 成功则为 201 updated DTO，若恢复遇到暂时性存储/DB 错误则为 503 `storage_unavailable`。 |
| GET /documents/{id} | 文档元数据、当前 revision 和是否可检索；pending/failed Document 可见。 | DocumentDetail `{document,currentRevision,isRetrievable}`。 |
| GET /documents/{id}/chunks | 可选 revisionId；仅返回有 Parsed Sections/Chunks 的 revision，按 sectionOrder、chunkOrder 排序。 | {revision, sections:[{..., chunks:[...]}]}；无 chunks 返回空树，不映射到其他文件的 fixture。 |
| POST /documents/{id}/process | 仅允许内置 `fixture_demo_retry` 或状态为 `uploaded_unprocessed` 的用户文档；必须带 Idempotency-Key；原子创建 attemptNumber=1 的 `demo_trace` Run，不改变文档/Revision 状态或 Sections/Chunks。 | 202 {run, document}。 |
| POST /documents/{id}/retry | 仅允许对应 Document 的 demo_trace attempt 1 已失败且 attempt 2 不存在；必须带 Idempotency-Key；原子创建唯一 attemptNumber=2 的 Run，不改文档/fixture 内容。其他状态返回 409 invalid_state_transition。 | 202 {run, document}。 |
| POST /retrieval/debug | {knowledgeBaseId, query, documentIds?, topK?} + Idempotency-Key；query 1–4000 字符，topK 默认 5、范围 1–20。提供 documentIds 时每个 ID 都必须属于该 KB 且为 ready fixture，否则返回 422 invalid_request。同步执行并记录 completed `retrieval` Run，同一事务持久化有序 `run_started`、`retrieval_completed`、`run_completed` 事件。 | 201 {runId, mode, query, evidence[]}；仅从 ready fixture revisions 返回。 |
| POST /chat/sessions | {knowledgeBaseId} 创建会话。 | 201 Conversation。 |
| GET /chat/sessions/{id} | 返回有序 messages 和进行中的 Run ID。 | ConversationDetail `{conversation,messages,activeRunId}`。 |
| POST /chat/sessions/{id}/messages | {question, topK?} + Idempotency-Key；question trim 后为 1–4000 字符；一个 session 同时只允许一个 active answer Run。 | 202 {userMessage, assistantMessage, run}；客户端随后订阅 Run SSE。 |
| GET /runs/{id} | Run 当前状态和事件快照；afterSequence 默认为 0、必须 ≥0 且不大于 throughSequence；limit 默认 50、范围 1–500，越界游标返回 422 invalid_cursor。 | {run, events[], throughSequence, nextAfterSequence?}。 |
| GET /runs | 最近运行分页列表；可按 knowledgeBaseId/kind/status 过滤；createdAt 降序、id 降序作为稳定次序。 | Page<Run>。 |
| GET /runs/{id}/events/stream | SSE；Last-Event-ID 必须属于路径中的 Run，sequence 必须在 0..throughSequence，否则返回 400 invalid_sse_cursor。 | text/event-stream。 |
| GET /providers | 读取启动时创建的 adapter registry 状态。 | ProviderStatus[]，含 profile/mode/registered/selected/available，不含 secrets。 |

Idempotency-Key 限 128 个可打印 ASCII 字符，作用域唯一键为 `(operation_type, owner_id, key)`：上传与检索 owner 是 KB，demo trace owner 是 Document，问答 owner 是 Conversation。fingerprint 是规范化 path/body 字段及上传文件 SHA-256 的组合摘要（不存原文）；本机单进程按 scope+key 加 keyed lock，数据库唯一约束作为最终保护。先查已有幂等记录，只有新操作才申请 dispatcher 容量；同 key 重放不占新槽。并发同 key、同 fingerprint 的请求返回同一操作状态/资源（运行中返回原 202，结束后返回资源当前终态）；竞争失败方删除自己的临时上传文件。不同 fingerprint 返回 409 `idempotency_key_conflict`。每个新的 upload key 即使字节相同也创建独立 Document 和初始 Revision，不按文件名或哈希合并；后续 Document 新 Revision 必须由显式指定 Document 的新路由创建。终态 key 在资源生命周期内保留；Stage A 不删除资源。Stage A 没有真实解析/重处理路由；process/retry 只生成明确标注的 demo_trace，不解析内容、不改变文档状态。

### 5.3 状态与失败语义

Run 状态唯一使用 queued → running → completed|failed，另允许 queued → failed 用于无法启动/进程重启；completed/failed 均为终态。Stage A 由 FastAPI lifespan 启动单进程 `InProcessRunDispatcher`：有界待处理队列容量 32、单 worker。Chat/process 用例先按 key 查询幂等记录；仅新操作预留队列槽。队列槽预留与 supervisor-owned task 调度之间不含 await/cancellation point；该 task 由 dispatcher 强引用，reservation、DB transaction、commit 与 enqueue 整段不受 HTTP handler cancellation 影响。已预留槽确保正常入队不失败。若发生意外 dispatch 错误，一个事务将 Run 标为 failed 并追加 `run_failed`；仅当 kind=answer 时同步将关联 assistantMessage 标为 failed。所有普通事件写入及状态迁移都在事务内确认 Run 仍为 queued/running；终态事件与终态迁移原子提交，终态后拒绝迟到事件或结果写入。事务失败则释放预留槽；进程恰在提交后退出时，启动 reconciliation 先处理 `upload_pending`：按摘要验证 staged/final 文件，存在有效 staged 文件时原子 rename，随后 finalize Document/Revision/Run 与完成事件；无法恢复时将资源与 upload Run 一并标失败。完成上传恢复后，再把其余遗留 queued/running dispatcher Run 标记失败，仅对 answer Run 更新 assistantMessage。浏览器断连不会取消已提交的 Run。应用关闭先等待 dispatcher worker 最多 5 秒，超时则取消并等待 dispatcher-owned task 退出，随后只将仍 queued/running 的 dispatcher Run（kind=`answer`/`demo_trace`）标为 `failed/process_interrupted`，仅对 answer Run 更新 assistantMessage。upload Run 不归 dispatcher 所有；进行中的上传保持 pending，由启动时的 upload-first reconciliation 恢复或失败。运行中不可再 retry。每个 Document 通过 `(document_id, attempt_number)` 唯一约束只允许 demo_trace attempt 1 与 attempt 2 各一次；并发不同 key 的竞争请求只有一个创建成功，其余返回 409 `invalid_state_transition`。服务重启时发现 queued/running 的 Run，追加安全 `run_failed` 事件；不让 UI 永久停在运行中。

| 资源 | Stage A 状态 | 触发规则 |
| --- | --- | --- |
| 用户上传 Document / DocumentRevision | upload_pending → uploaded_unprocessed 或 upload_failed | Document 与初始 Revision 同步可见；pending/failed 都可由列表与详情读取；成功 finalize 后才可检索。失败重传用新 key 创建新的 Document 与初始 Revision，不会在旧 Document 上制造新版本。 |
| 内置 fixture Revision | ready | 随幂等 seed 初始化，Sections/Chunks 都指向该 revision。 |
| demo_trace Run | queued → running → completed|failed；queued 也可因启动失败转 failed | 可用于 `fixture_demo_retry` 或 `uploaded_unprocessed` 用户文档；attempt 1 稳定失败，错误码 `demo_transient_error`；唯一 retry attempt 2 稳定成功。DB 唯一约束 `(document_id, attempt_number)` 防止并发创建重复轨迹。Run 只演示状态与事件，不解析内容、不改变 Document/Revision 状态或 Sections/Chunks。 |
| Chat Message | userMessage、queued assistantMessage 与 Run 在同一事务创建；assistantMessage 随事件变为 streaming，Run 终态时变为 completed 或 failed。 | 同一会话串行；active Run 存在时创建消息返回 409 conversation_busy。 |

同一 Conversation 同时最多一个 active answer Run，由数据库 partial unique index 原子保障；userMessage（runId=null）、queued assistantMessage（runId=Run.id）与 Run 在同一事务创建，冲突整体回滚并返回 409 conversation_busy。消息序号使用 `(conversation_id, sequence)` 唯一约束。无 Evidence 时 AnswerProvider 返回固定 abstention 答复“当前知识库中没有找到可引用的资料。”；系统可发该固定文本的 `answer_delta`，不返回 Citation，Run 正常 completed，结果标记 abstained。失败 Run 的 assistantMessage 状态为 failed，内容为空并带可展示的安全失败提示；不保存部分答案。

Problem DTO 固定为 type,title,status,detail,code,requestId,retryable,runId；runId 必需但可空。分页游标 API 越界返回 422 `invalid_cursor`；SSE 请求头格式错误或游标超前时返回 400 `invalid_sse_cursor`，避免同一错误码映射多个状态。共享错误表：

| code | HTTP | retryable | 用途 |
| --- | ---: | --- | --- |
| invalid_request | 422 | false | DTO/字段校验失败；允许扩展名与文件字节签名不匹配时用 file_signature_mismatch |
| resource_not_found | 404 | false | KB/Document/Conversation/Run 不存在 |
| invalid_state_transition | 409 | false | 不允许的状态操作 |
| idempotency_key_conflict | 409 | false | key 已存在但请求内容不同 |
| conversation_busy | 409 | true | 该会话已有 active Run |
| file_too_large | 413 | false | 超过 UPLOAD_MAX_BYTES |
| unsupported_file | 415 | false | 文件扩展名不在 allowlist 或格式已识别但不支持 |
| file_signature_mismatch | 422 | false | 扩展名在 allowlist 内，但字节签名与扩展名不匹配 |
| invalid_cursor | 422 | false | Run 事件页游标负数或超过当前 throughSequence |
| invalid_sse_cursor | 400 | false | SSE Last-Event-ID 格式非法、不匹配路径 Run 或超前 |
| runner_busy | 503 | true | 有界本地 dispatcher 队列无空位；在写入 Message/Run 前拒绝请求 |
| storage_unavailable | 503 | true | 文件持久化失败 |
| internal_error | 500 | false | 其他失败；正文仅含安全文案 |

FastAPI validation、未捕获异常和 storage 异常统一映射到该 Problem shape。内部属性名为 `request_id`；每个 HTTP response 都带 `X-Request-ID` header，Problem JSON 固定带 `requestId` 与必需 nullable `runId`。服务日志按同一 request_id 关联诊断信息。客户端永远看不到 stack trace、原始异常、路径、密钥或 provider 响应正文。

### 5.4 RunEvent 与 SSE

每个 event 的 JSON 是 allowlist schema：runId, sequence, eventType, phase, status, timestamp, payload；SSE 帧 id 为 {run_id}:{sequence}，event 取 eventType，data 为同一条 JSON。(run_id, sequence) 唯一，序号在 repository 同一事务中分配并落库；重复 append 由调用方提供的稳定 source_event_key 在同一 run 内去重。SSE 只发布已提交的事件。

| eventType | 允许的 payload |
| --- | --- |
| run_started | kind, mode |
| phase_updated | phase, status, summary；summary 最多 240 字符 |
| answer_delta | messageId, text；text 每帧最多 1024 字符 |
| citation_added | messageId, revisionId, chunkId, page, quote；quote 最多 600 字符 |
| upload_completed | documentId, revisionId, storedBytes；不含原文件名路径或内容 |
| run_completed | resultStatus, messageId? |
| run_failed | safeErrorCode, retryable |
| retrieval_completed | evidenceCount, evidenceRefs；最多 20 个 `{revisionId, chunkId, rank, score, quote}` 引用，quote 最多 600 字符 |

事件 sequence 从 1 开始，0 表示尚未收到事件；初次 SSE 连接从 0 开始 replay。`Last-Event-ID` 必须是当前路径 Run 的 `{run_id}:{sequence}` 且 sequence ≥0、不大于当前 throughSequence，否则返回 400 `invalid_sse_cursor` 并关闭连接。自动重连严格从已确认序号之后 replay，再持续查询持久化事件直到 Run 终态。客户端按 SSE ID 去重。Run detail 的 afterSequence 是 exclusive cursor，响应 throughSequence 标出快照边界；断开后请求事件页或重新订阅，不依赖“先拿列表再听新事件”的有缝流程。每 15 秒发送心跳注释；Web/代理不得缓存或缓冲 SSE。Run 完成后重连会补齐缺失事件并结束。

Chat 流先 POST /messages 获得 run.id，然后 GET EventSource 订阅 Run，因此浏览器重连可自动带 Last-Event-ID。会话只允许一个 active answer Run，避免并发增量文本、Citation 与消息次序交错。

## 6. 上传、fixture 和文件一致性

Stage A 接受 PDF、DOCX、Markdown、TXT，默认 UPLOAD_MAX_BYTES=26214400（25 MiB）；配置可收紧，不能超过硬上限。扩展名和格式签名同时校验：PDF %PDF-，DOCX 为含 word/document.xml 的 ZIP，Markdown/TXT 是可解码 UTF-8。DOCX 读取 ZIP 中央目录时限制最多 10,000 entries、单 entry 解压后 ≤50 MiB、总解压 ≤200 MiB、压缩比 ≤100；不展开外部链接或宏。HTTP Content-Type 仅作为提示，不作为安全校验。文件名只用于显示，Unicode 规范化、去除路径分隔符/控制字符、最长 255 UTF-8 bytes；storage key 使用服务端 UUID。请求流边读边写同卷 `.part` 临时文件，同时计数、校验、计算 SHA-256；不缓存整个文件到内存。

上传写入与幂等处理的唯一顺序：
1. 将 multipart 流直接写入 uploads 同卷的随机 `.part` 文件；边读边限制大小、校验扩展名/签名、计算 SHA-256 和规范化请求 fingerprint，随后 flush/close。任何流式写入或校验失败都清理 `.part` 并返回对应 Problem；此阶段不创建 Document、Run 或幂等记录。未提交元数据的 `.part` 文件不可被 API 读取。
2. 取得 `(operation_type, KB ID, Idempotency-Key)` keyed lock，再查已有幂等记录。fingerprint 不同则删除本次 `.part` 并返回 409。相同 key 已成功则删除本次 `.part` 并返回当前 Document/Revision/Run（201）；已失败则重放原 Problem；仍 pending 时优先校验已有 staged/final 文件的摘要并尝试 finalize：恢复成功返回 201 updated DTO，仍由进行中的操作持有时返回 202 pending DTO，暂时性存储/DB 错误返回 503 `storage_unavailable` 并保留待恢复记录。重放和冲突请求永不覆盖原文件。
3. 只有没有已有 key 的新操作才进入一个数据库事务，同时创建 KB-owned Document、其初始 `upload_pending` Revision、`running` 状态的 upload Run（并追加 `run_started`）与幂等记录；幂等记录保留私有 staging key 与摘要以供恢复。事务失败则删除本次 `.part`；事务提交后 Document/Revision 可由 list/detail 读取，状态为 upload_pending 且不可检索。
4. 将 `.part` 用原子 rename 移至服务端生成的不透明 final key；随后一个数据库事务设置 Revision 与 Document 为 `uploaded_unprocessed`、Run completed、追加 `upload_completed`/`run_completed` 并提交。只有成功返回 201，且仅该状态表示文件已完整保存。
5. DB reservation 完成后的 rename 失败时删除临时文件，将 Document/Revision 标记 `upload_failed`、Run 标记 failed，并返回含 runId 的 `storage_unavailable` Problem；相同 key 重放原失败结果，想重新上传须用新 key 创建新 Document 及初始 Revision。reservation 前的临时写入错误按步骤 1 处理，不产生可见资源。
6. 若 rename 成功但 finalize 事务失败，保留 upload_pending 资源和 final 文件，返回含 runId 的 503 Problem。相同 key 重放会按记录的摘要验证 final 文件并重试 finalize，成功时返回 201 updated DTO；应用启动时先运行上传 reconciliation：按记录摘要验证 staged/final 文件，完整则 finalize，否则将 Document、Revision 和 upload Run 一起置为失败；此步骤完成后才将其他未完成 dispatcher Run 标为进程中断。清理没有 DB 记录的过期 `.part` 文件；任何未知文件都不会公开下载。

Fixture 与用户上传分离：fixture 有固定 fixture_* ID 与预生成 revision/Section/Chunk；seed 幂等，禁止覆盖同名 user record。POST process 在 UI 明确标注“运行 Demo 处理轨迹”：fixture 与 `uploaded_unprocessed` 用户文档都只生成安全状态事件，不执行 parser，不修改 Document/Revision 状态、fixture readiness 或 Sections/Chunks。attempt 1 固定失败、唯一 retry attempt 2 固定成功，旧 Run/事件保留；“成功”只代表合成演示 Run 完成，不代表文件解析成功。用户上传不会依据文件名或内容哈希映射到 fixture，不会得到 fixture 的 Section、Chunk、Evidence 或引用。Chunk 页面只展示它明确所属的 DocumentRevision。Stage A 上传完成只说明字节被安全保存，不等于解析、索引或可检索。

## 7. 工作台页面与端到端演示

视觉参考采用用户附件中的蓝色调、清晰分区和能力卡片布局。图片里的 OCR、向量检索、权限等标签不代表当前已经实现。可交互内容都从同一 API 来，不在 Vue 页面内另做一套 mock DTO。

| 页面 | 主要交互 | 空/异常与真实性说明 |
| --- | --- | --- |
| 知识库首页 | 列表、最近 Run、新建/进入。 | seed 一个 Demo KB；空列表给创建指引。 |
| 文档管理 | 查看 fixture 与用户上传；上传文件；为 fixture 或用户上传启动明确标注的 Demo 处理轨迹/retry。 | 用户上传明确显示“已保存，尚未解析”；即使 Demo Run 成功仍保持未解析；格式/大小错误和存储失败可通过修正后重新上传恢复。 |
| Chunk 观测 | 按 revision 查看 Section→Chunk、页码、标题路径和文本片段。 | 用户上传 revision 返回空结构并显示“暂无解析结果”；不能跨文档补 fixture 内容。 |
| 检索调试 | 输入 query、可选 KB/文档过滤；看 fixture Evidence、mock 分数和来源定位。 | 只检索 ready fixture revision；无结果显示空 Evidence 状态。 |
| Agent 问答 | 选择 KB 与示例问题；提交后订阅 run SSE；查看答案、阶段摘要和 Citation。 | 无 Evidence 输出固定资料不足答复，不附 Citation；断流可续传。 |
| 运行详情 | 通过 run ID 查看状态、时长和事件页/流。 | 无记录、运行中、失败、断线恢复；只有安全错误码和摘要。 |
| Provider 状态 | 查看生效 profile、已选 adapter 与 mode。 | Stage A 只显示 mock；不查询或回显密钥。 |

Demo 走查链路：打开内置 Demo KB → 选择一个 fixture 文档查看已固定的 Chunk → 对 `fixture_demo_retry` 运行 Demo 处理轨迹并演示重试 → 调试检索 → 发起问答并查看引用 → 断开/恢复 SSE → 打开同一 Run 详情。另上传一个文件，对其启动并重试 metadata-only Demo trace，确认即使 Run 成功，上传文件仍显示“尚未解析”且 Chunk 为空。两条轨迹都只演示事件/重试 UI，不改变 fixture ready 内容或用户文件状态。

所有 provider result、Evidence、answer 和分数持续显示 DEMO/MOCK。内置 fixture 不能标记成真实企业资料，也不能描述为检索准确率达标。用户的附件只用于界面色彩和区块参考，不把图片能力标签视为已实现需求。

## 8. 数据库、运行配置与 Compose

### 8.1 本机无 Docker

本机使用项目目标 Python 3.13.15、Node.js 24.21.0 和本地 SQLite 文件；上传目录为 data/uploads/。当前机器检测到 Python 3.14.2、Node.js 24.13.0 和 SQLite 3.50.4，这些是环境观察值，不是项目锁定目标。开始运行项目前需准备目标解释器/Node 版本；实现代码保持 Python 3.13 兼容，不依赖 3.14 专有语法。

同一套配置读取 DATABASE_URL、UPLOAD_DIR、UPLOAD_MAX_BYTES、RAG_MODE=mock、VITE_API_BASE_URL 和 WEB_ORIGINS。本机 API 默认绑定 localhost；Vite 对 /api/v1 做代理；数据目录在 .gitignore。

本机 schema 初始化执行明确命令 uv run alembic upgrade head，之后再启动 FastAPI。API 不自行 create_all() 或迁移。SQLite 每个连接执行 PRAGMA foreign_keys=ON，就绪检查验证 alembic_version 达到应用要求的 revision。

### 8.2 Compose 演示模式

Compose 服务为 web、api、一次性的 migrate 与 postgres。PostgreSQL 用 18.6 镜像和 named volume，API 使用 psycopg[binary] 3.3.6 与 `postgresql+psycopg://` URL；上传 volume 绑定到 API。Postgres 健康检查通过后，migrate 服务运行唯一迁移命令；API 只有在 migration 服务成功且 DB ready 时启动。API readiness 再确认 schema revision。Compose 端口只发布到 loopback：Web 127.0.0.1:4173，API 127.0.0.1:8000；PostgreSQL 不发布宿主机端口，仅 Compose 网络可达。API 单进程运行，Stage A 不扩成多个 worker。

.env.example 提供所有配置名称、默认值和本地说明；不提交真实密钥。Compose 绑定用户 uploads 与 DB data 持久卷并明确文件权限。/health/live 只报告进程存活；/health/ready 检查数据库连通性和 schema revision。Web 到 API 的 browser-visible URL、CORS allowlist、SSE timeout/no-buffer 行为明确配置。Compose 的本地 PostgreSQL 与 SQLite 是各自独立的数据集；不隐式迁移用户记录。需要切换时必须另行提供显式数据导入方案。

Alembic 是唯一 schema authority。禁止首次启动调用 ORM create_all()；禁止每个 API 进程同时升级 schema。外键删除策略统一为 RESTRICT 或软删除，Stage A 无硬删除 endpoint；迁移避免循环外键。SQLite 与 PostgreSQL 均必须可应用同一 Alembic revision，并对文档父级、revision 身份、RunEvent 序号、`(operation_type, owner_id, key)` 幂等键、`(conversation_id, sequence)` 消息序号和每会话一个 queued/running answer Run 施加等价约束。

## 9. 阶段 A 验收边界

- 七类页面使用同一版本化 API；API DTO/OpenAPI/生成 TS 类型一致，生成检查无 drift。
- fixture 数据身份稳定且只读；用户上传保留原文件与元数据，但清楚显示未解析且不可检索。
- Citation/Evidence 能还原到不可变的 revision、Section 和 Chunk。
- Run 状态合法；事件先持久化、序号唯一；SSE 断连后按 cursor 补发，不缺不重。
- 无 Evidence 触发固定 abstention，不生成来源伪装；Mock mode 标识始终可见。
- 本机 SQLite 和 Compose PostgreSQL 使用同一 Alembic revisions；API readiness 等待 schema 版本一致。
- 加载、空、错误、上传失败、无证据和流断开状态可理解并可恢复；浏览器、错误响应和 Provider 状态不暴露 secrets 或内部异常。

阶段 A 不验收真实解析、OCR、Recall@K、Answer 质量、生产异步调度、权限、多租户或高可用。

## 10. 风险、延后事项与触发条件

| 事项 | 当前处理 | 复核触发条件 |
| --- | --- | --- |
| Stage B 真实解析/OCR/Chunking | 稳定端口已进入架构；Stage A 只读 fixture。 | 取得第一批可授权语料后，设计格式支持、解析质量与失败恢复。 |
| 向量/关键词引擎 | KnowledgeRetriever 已稳定；底层向量与 BM25/RRF 延后。 | 有真实中文语料、规模和运维约束后，经评测在 Milvus/pgvector 等中选择。 |
| RAG 质量评测 | Stage A 不报告检索质量。 | Stage B 准备至少 30 条黄金问题，报告 Recall@5、citation validity、no-answer recognition；建议首轮 Recall@5 ≥0.80 并按语料校准。 |
| 持久异步 Worker | Stage A 为本地单 API 进程的 mock flow；异常重启时把未完成 Run 标 failed。 | 真实处理跨越请求生命周期、需要并行工作或可靠重试前接入持久任务队列。 |
| LangGraph 固定流程成本 | 本阶段确定采用 LangGraph，不启 checkpoint。 | 实现评估若该固定流程确实只增加复杂度，记录新的架构评审后再改决策。 |
| 认证与数据隔离 | Stage A 是本机演示，无身份/多租户承诺。 | 任何共享部署前加入认证、权限模型与审计。 |
| 本机 Python/Node 与目标版本差异 | 记录环境实测值；依赖清单采用 Stack 表目标版本。 | 准备 3.13.15 与 Node 24.21.0 运行环境后检查启动路径。 |

## 11. 实施顺序

1. 初始化 apps/api、apps/web、配置样例和依赖锁文件；加入 OpenAPI 生成命令与 Alembic 基线。
2. 建立 Domain、Repository/FileStore/provider ports、适配器组合根、Demo KB/fixture 和 idempotent seed。
3. 建立 API DTO、统一 error map、knowledge/document/upload/Chunk endpoints 与 SQLite/Compose 配置。
4. 完成知识库、文档管理和 Chunk 观测页面；明确区分 fixture 解析结果与用户上传未解析文件。
5. 完成检索调试、LangGraph mock answer、Chat message/Runs、持久事件和 SSE replay。
6. 建立 Provider 状态、Run 详情、Compose/health/readiness、OpenAPI docs、README 和可重复 Demo walk-through。
7. 阶段 A 实现完成后，按独立的 UX/交付检查清单走查页面可达性与状态表现；该走查不能把 mock 标成真实能力。

## 12. 版本依据与上游来源

下表按 2026-09-23 可见的稳定版本作为锁文件候选。Python 3.13.15 是兼容优先选择，而不是最新 Python 主版本；SQLite 则由解释器构建提供。

| 组件 | 方案版本 | 来源/选择依据 |
| --- | --- | --- |
| Python | 3.13.15 | LangGraph 1.2.12 元数据列出至 3.13；本机现装 3.14.2 不作为项目兼容承诺。 |
| FastAPI / Pydantic | 0.141.1 / 2.13.5 | 官方 releases；Pydantic v2。 |
| SQLAlchemy / Alembic | 2.0.54 / 1.20.0 | 官方稳定 release；使用 SQLAlchemy 2.0 兼容线。 |
| LangGraph | 1.2.12 | 官方 release；本阶段不启用 checkpoint/CLI。 |
| Vue / TypeScript | 3.5.43 / 6.0.3 | Vue/Volar 当前工作流需要稳定 TypeScript API；TypeScript 7 公告建议该类工具链暂用 6。 |
| Vite / Node.js | 8.3.0 / 24.21.0 | Vite 8 支持 Node 24 LTS。 |
| @hey-api/openapi-ts | 0.99.0 | OpenAPI 3 代码生成器；精确锁版本并仅启用类型插件，避免 TS peer 范围与 Vue/Volar 冲突。 |
| psycopg[binary] | 3.3.6 | PostgreSQL 适配驱动；DATABASE_URL 使用 postgresql+psycopg://。 |
| PostgreSQL | 18.6 | Compose DB target。 |
| SQLite | Runtime-provided | sqlite3.sqlite_version 启动诊断输出实际值；不是项目独立 pin。 |

官方版本依据：[Python 3.13.15](https://www.python.org/downloads/release/python-31315/)、[FastAPI releases](https://github.com/fastapi/fastapi/releases)、[Pydantic 2.13.5](https://github.com/pydantic/pydantic/releases/tag/v2.13.5)、[SQLAlchemy 2.0.54](https://github.com/sqlalchemy/sqlalchemy/releases/tag/rel_2_0_54)、[Alembic 1.20.0](https://github.com/sqlalchemy/alembic/releases/tag/rel_1_20_0)、[LangGraph 1.2.12 metadata](https://github.com/langchain-ai/langgraph/blob/1.2.12/libs/langgraph/pyproject.toml)、[Vue 3.5.43](https://github.com/vuejs/core/blob/main/CHANGELOG.md#3543-2026-09-17)、[TypeScript 6.0.3](https://github.com/microsoft/TypeScript/releases/tag/v6.0.3)、[TypeScript 7 与 Vue/Volar 工具链说明](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)、[Vite 8.3.0](https://github.com/vitejs/vite/releases/tag/v8.3.0)、[Node.js 24.21.0](https://nodejs.org/en/download/archive/v24.21.0)、[PostgreSQL 18.6](https://www.postgresql.org/docs/release/18.6/)、[@hey-api/openapi-ts 0.99.0](https://www.npmjs.com/package/@hey-api/openapi-ts)、[psycopg-binary 3.3.6](https://pypi.org/project/psycopg-binary/3.3.6/)。

## 13. References

- 源方案：[BMAD-企业知识库RAG项目方案.md](../../../../outputs/BMAD-企业知识库RAG项目方案.md)
- 技术架构脊柱：[ARCHITECTURE-SPINE.md](ARCHITECTURE-SPINE.md)
- 上游项目：[MaxKB](https://github.com/1Panel-dev/MaxKB)、[FastGPT](https://github.com/labring/FastGPT)、[RAGFlow](https://github.com/infiniflow/ragflow)、[Dify API](https://github.com/langgenius/dify/blob/main/api/README.md)

