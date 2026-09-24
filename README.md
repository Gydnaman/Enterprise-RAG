# 知引 · 企业知识工作台 Stage A

这是一个可本地运行的企业知识库 RAG 工作台演示，使用 FastAPI + Vue。OpenAPI 是前后端共享契约；SQLite 用于本机开发，Compose 提供 loopback-only PostgreSQL 演示环境。

## 当前能力与演示边界

- 提供知识库、文档、Chunk 观测、检索调试、Agent 问答、Run 详情和 Provider 状态页面。
- 内置只读 Fixture 提供可回溯的 Revision、Section、Chunk、Evidence 与 Citation。
- 所有演示结果都标注为 **DEMO / MOCK**。检索分数不代表准确率。
- 用户上传支持 PDF、DOCX、Markdown、TXT，最大 25 MiB；上传只做大小、扩展名、签名校验并安全保存为 `uploaded_unprocessed`。Stage A 不解析上传内容，也不会从用户上传创建 Section/Chunk 或 Evidence。
- Demo process/retry 只演示持久 Run 状态。attempt 1 固定失败，attempt 2 固定成功；成功不代表文件解析成功。
- 不连接真实 LLM、OCR、向量库或外部服务；没有认证、多租户或生产队列。

## 本地启动（SQLite）

要求 Python 3.13.15、Node.js 24.21.0、pnpm 11.19.0 与 uv。复制 `.env.example` 到 `.env`，按需调整上传目录和 CORS 来源。

```powershell
uv lock --project apps/api
pnpm install
uv run --project apps/api --env-file .env alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api --env-file .env uvicorn rag_workbench.main:app --app-dir apps/api/src --host 127.0.0.1 --port 8000 --workers 1
```

在另一个终端运行：

```powershell
pnpm --dir apps/web dev
```

打开 <http://127.0.0.1:5173>。SQLite 文件位于 `data/workbench.db`，用户上传字节位于 `data/uploads/`。首次启动 API 时，fixture 会按稳定 ID 幂等写入。Schema 只通过显式 Alembic upgrade 创建；API 不会运行 ORM `create_all()`。

## Compose 演示

复制 `.env.example` 到 `.env` 后，从仓库根目录运行：

```powershell
docker compose up --build
```

浏览器访问 <http://localhost:4173>，API 为 <http://localhost:8000>。Web 与 API 仅绑定 loopback；PostgreSQL 只在 Compose 网络中可达。唯一的 migrate 服务成功后 API 才会启动。Compose PostgreSQL 与 SQLite 是各自独立的数据集。

停止并保留数据：

```powershell
docker compose down
```

## 演示路径

1. 打开内置 Demo Knowledge Base，进入“文档管理”。
2. 查看只读 Fixture 的 Chunk；对“企业知识工作台手册”运行 Demo 处理轨迹，再打开 attempt 1 的 Run 并重试。
3. 上传一个小型 Markdown/TXT 文件，确认状态为“已保存 · 尚未解析”；查看它的 Chunk 页面为空，再对该文件运行 Demo trace。
4. 在检索调试中输入“上传文件会自动解析吗”，查看 DEMO Evidence 及其 revision/chunk 来源。
5. 创建问答会话并提问，查看 Citation、答案 Run 和持久事件流；刷新或断开连接后浏览器会继续接收事件。
6. 打开 Provider 状态，确认只有固定 mock adapter 被选中。

## API 契约与常用检查

FastAPI DTO 是 API schema 来源：

```powershell
uv run --project apps/api python -m rag_workbench.export_openapi
pnpm api:generate
pnpm api:check
pnpm typecheck
uv run --project apps/api alembic upgrade head
```

OpenAPI JSON 位于 `docs/api/openapi.json`；生成 TypeScript 类型位于 `apps/web/src/api/generated/types.gen.ts`。`/health/live` 检查进程，`/health/ready` 检查数据库连接与 schema revision。统一 Problem 响应包含 request ID 和安全错误码；服务端不返回本地存储路径、密钥或异常栈。
