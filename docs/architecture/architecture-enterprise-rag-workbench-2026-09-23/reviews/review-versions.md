# BMAD 技术方案评审：版本与运行时兼容性

- 评审对象：`ARCHITECTURE-SPINE.md` 的 Stack 表、AD-8，以及 `SOLUTION-DESIGN.md` 第 3、7、9、11 节
- 评审日期：2026-09-23
- 评审范围：锁定版本是否为当日上游稳定版本；Python 3.14 与 FastAPI/Pydantic/SQLAlchemy/LangGraph；Node 与 Vite；PostgreSQL 与 SQLite 的兼容和声明方式
- 结论：**有条件通过，修订后再作为开工基线。** 没有发现 FastAPI/Pydantic/Vite/PostgreSQL 版本之间的硬性不兼容；但当前清单漏掉多个已发布补丁版本，LangGraph 对 Python 3.14 的上游支持证据不足，SQLite/PostgreSQL 共用迁移的关键行为尚未落到实现要求。

## Findings

### F-1（需修订）版本快照不是 2026-09-23 的当前稳定版

方案将版本快照称作“2026-09-23 可见的上游稳定版本”，但若将它们当作此日开工精确基线，有以下版本漂移：

| 技术 | 方案 pin | 2026-09-23 上游情况 | 评审意见 |
| --- | --- | --- | --- |
| Python | 3.14.2 | Python 3.14.7 已于 2026-08-05 发布 | 更新为 3.14.7，或明确该版本只是当前已安装解释器、而非推荐基线。 |
| FastAPI | 0.141.1 | 0.141.1 是当前稳定 release | 保留。官方版本元数据支持 Python 3.14。 |
| Pydantic | 2.13.5 | 2.13.5 是当前稳定版；2.14 为 beta | 保留。PyPI 显示 pydantic-core 2.46.5 提供 CPython 3.14 wheel。 |
| SQLAlchemy | 2.0.52 | 2.0.54 于 2026-09-15 发布，2.0 系稳定线；2.1 仍为 RC | 推荐改为 2.0.54。上游发布记录把 2.0.54 标为 latest。 |
| LangGraph | 1.2.12 | 1.2.12 是 2026-09-21 发布的当前稳定版 | 版本可保留，但 Python 3.14 支持声明见 F-2。 |
| Vue | 3.5.43 | 2026-09-17 发布，当前稳定版 | 保留。选 3.5 stable 而非 3.6 RC 是合适的。 |
| TypeScript | 6.0.2 | 6.0.3 为更新的 6.0 稳定补丁；7.0.2 是已发布新主版本 | Vue 方案推荐用 6.0.3；不要只因 7.0.2 更新就升级 Vue 工具链，见 F-3。 |
| Vite | 8.3.0 | 2026-09-10 发布的稳定版 | 保留。官方 Node 要求为 20.19+ 或 22.12+，24.x 满足。 |
| Node.js | 24.13.0 | 24.21.0 已发布于 24 LTS 线；Node 26 是 Current 线 | 推荐 24.21.0 LTS，24.13.0 的版本 pin 已过时。 |
| PostgreSQL | 18.6 | PostgreSQL 官方 2026-08-13 发布的当前 18 系稳定更新 | 保留；不应把 18.5 写入配置（官方说明 18.5 未发布）。 |
| SQLite | 3.50.4 | 官方最新发布为 3.53.4（2026-07-24） | 更新方案记录，或注明这是已检查的某一特定本地 Python 构建值；Python 本身不固定跨机器的 SQLite 库版本。 |

建议在锁文件/容器标签中明确真正需要复现的运行时与包版本，并将“建议稳定基线”与“当前这台机器实测值”分开记录。更新时以 `pyproject.toml`/lock、`package.json`/lock、Compose image tag 为准，避免仅更新文档数字。

### F-2（需验证）LangGraph 1.2.12 与 Python 3.14 的声明不一致

FastAPI 已声明 Python 3.14 支持；Pydantic 2.13.5 的包元数据包含 Python 3.14，PyPI 上的 pydantic-core 2.46.5 也发布了常规 CPython 3.14 wheels；SQLAlchemy 2.0.52 的上游发布说明称已加入并测试 Python 3.15 支持。因此这些包与 Python 3.14.7 未见版本元数据层面的障碍。

但 LangGraph 1.2.12 的 `pyproject.toml` 虽声明 `requires-python >=3.10`，其 Python classifiers 只列到 3.13，没有列 3.14；它的开发依赖组还对 `python_version < '3.14'` 条件安装 `langgraph-cli` 相关包。这不能证明核心 LangGraph 在 3.14 不可用，但意味着方案不能把它说成已有明确的 3.14 支持/测试覆盖。

**建议：**若保留 Python 3.14.7，开工时必须在该版本上做干净环境的依赖安装与最小 LangGraph invoke/stream 冒烟检查，并把结果记录进验收；若希望只选有上游 classifier 的路径，则改用 Python 3.13.x。当前阶段 A 不需要 LangGraph CLI，因此该条件标记主要影响开发工具/测试依赖，不是已证实的运行时阻断。

### F-3（需修订）Vue 的 TypeScript 选择应留在 6.0 线，但补丁要更新

TypeScript 7.0.2 已是新的稳定主版本，TypeScript 6.0.3 是 6.0 稳定线的新补丁。微软 TypeScript 7.0 公告明确指出 Vue、MDX、Astro、Svelte 等依赖嵌入式语言服务的工作流目前仍需 TypeScript 6.0，因为 7.0 尚未提供工具（如 Volar）需要的稳定程序 API，并建议这些项目暂用 6.0。

**建议：**pin 改为 TypeScript 6.0.3；在 TypeScript/Volar 支持稳定前，不将 Vue 3.5 工作台切到 7.0.2。这样既修正过期补丁，也避免将“最新大版本”误当作整个工具链的兼容选择。

### F-4（需落实）SQLite 与 PostgreSQL 可用同一 SQLAlchemy Repository，但“相同迁移”不是自动成立

SQLAlchemy 2.0 的官方 dialect 文档将 SQLite 3.12+ 与 PostgreSQL 9.6+ 列为受支持版本，故草案所选 SQLite 3.53.4 / PostgreSQL 18.6 在版本范围内没有冲突。SQLAlchemy 2.0 也将 SQLite 和 PostgreSQL 列为内置 dialect。

但 SQLite 有需要显式处理的行为差异：外键约束默认不启用，必须在**每条连接**上执行 `PRAGMA foreign_keys=ON`（包括创建表前）；SQLite 不支持对约束单独 `ALTER TABLE`，相互依赖的外键会影响建表/删表与迁移。只写“共用 ORM/迁移、避免方言 SQL”不足以保证数据库行为相同。另外，spine 承诺“版本化迁移”，而方案第 7 节写成“第一次启动时创建表结构”，未明确迁移工具；SQLAlchemy 的 `metadata.create_all()` 不是历史版本迁移方案。

**建议：**明确采用 Alembic（及迁移版本管理规则），SQLite 连接创建时启用外键；避免循环外键；保持 DDL/默认值/索引在两库都能表达，并将相同迁移分别应用于全新 SQLite 和 Compose PostgreSQL。SQLite 版本应由运行时检测（如 `sqlite3.sqlite_version`）报告；如其版本本身是验收要求，就固定 Python 构建/镜像，而不要仅在方案中写一条版本号。

## 兼容性总表

- **Python 3.14.7 + FastAPI 0.141.1 + Pydantic 2.13.5：**元数据和上游发行证据支持；FastAPI release notes 已记录 Py3.14 支持，Pydantic/pydantic-core 在 PyPI 有 3.14 分类及平台 wheel。当前 Python pin 3.14.2 过时。
- **Python 3.14.7 + SQLAlchemy：**上游 SQLAlchemy 发布记录表明 2.0.52 已添加并测试 3.15 支持；2.0.54 是应优先采用的当前 2.0 稳定更新。建议仍用实际 Windows/Python 3.14 环境安装确认驱动组合。
- **Python 3.14.7 + LangGraph 1.2.12：**`requires-python` 下限允许，但 3.14 不在 classifiers 中，官方支持状态不明；按 F-2 冒烟验证或使用 3.13。
- **Node 24 + Vite 8.3：**Vite 要求 Node 20.19+ 或 22.12+，版本范围兼容。改 pin 至 24.21.0 LTS 以获得更新的 LTS 补丁。
- **Vue 3.5 + TypeScript：**Vue 3.5.43 可留；采用 TS 6.0.3，当前不建议 Vue/Volar 编辑器工作流直接切 TS 7。
- **SQLAlchemy + SQLite/PostgreSQL：**两个 dialect 和所列 DB 主版本均在 SQLAlchemy 官方支持范围；共用 Repository 可行，但连接 PRAGMA、迁移工具、SQL 方言及事务行为仍需应用约束和双库验证。

## 官方上游来源

- Python 3.14.7 release（2026-08-05）：https://www.python.org/downloads/release/python-3147/
- FastAPI release notes（0.118.3 记录 Python 3.14 支持，0.141.1 当前稳定版本）：https://fastapi.tiangolo.com/release-notes/
- Pydantic 2.13.5 release（2026-08-28）：https://github.com/pydantic/pydantic/releases/tag/v2.13.5
- pydantic-core 2.46.5 PyPI（Python 3.14 classifiers/wheels）：https://pypi.org/project/pydantic_core/2.46.5/
- SQLAlchemy 2.0.54 release（2026-09-15）：https://github.com/sqlalchemy/sqlalchemy/releases/tag/rel_2_0_54
- SQLAlchemy Python/数据库 dialect support：https://docs.sqlalchemy.org/en/20/dialects/
- SQLAlchemy SQLite foreign-key prerequisites与限制：https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support
- LangGraph 1.2.12 release：https://github.com/langchain-ai/langgraph/releases/tag/1.2.12
- LangGraph 1.2.12 package metadata：https://github.com/langchain-ai/langgraph/blob/1.2.12/libs/langgraph/pyproject.toml
- Vue 3.5.43 changelog/release：https://github.com/vuejs/core/blob/main/CHANGELOG.md#3543-2026-09-17
- TypeScript 6.0.3 release：https://github.com/microsoft/TypeScript/releases/tag/v6.0.3
- TypeScript 7.0 compatibility guidance for Vue/Volar：https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/
- Vite 8.3.0 release：https://github.com/vitejs/vite/releases/tag/v8.3.0
- Vite 8 Node.js support：https://vite.dev/blog/announcing-vite8
- Node.js 24 LTS release archive：https://nodejs.org/en/download/archive/v24.21.0
- PostgreSQL 18.6 announcement/release notes：https://www.postgresql.org/about/news/postgresql-186-1711-1615-1424-and-19-beta-3-released-3365/ https://www.postgresql.org/docs/release/18.6/
- SQLite current news and 3.53.4 release：https://www.sqlite.org/news.html https://www.sqlite.org/releaselog/3_53_4.html
