import type {
  ChunkTree, Conversation, ConversationDetail, Document, DocumentDetail, Evidence, KnowledgeBase,
  Message, PageDocument, PageKnowledgeBase, PageRun, PendingUpload, Problem, ProcessResult,
  ProviderStatus, RetrievalDebugResult, Run, RunEvent, RunSnapshot, SendMessageResult, UploadResult,
} from './generated/types.gen'

const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'

export class ApiError extends Error {
  constructor(public readonly problem: Problem) {
    super(problem.detail)
  }
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID()
}

const IDEMPOTENCY_STORAGE_KEY = 'rag-workbench.pending-idempotency-keys.v1'

function loadPendingKeys(): Map<string, string> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(IDEMPOTENCY_STORAGE_KEY) ?? '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return new Map()
    return new Map(Object.entries(parsed as Record<string, unknown>).flatMap(([identity, key]) =>
      typeof key === 'string' ? [[identity, key] as [string, string]] : [],
    ))
  } catch { return new Map() }
}

const pendingIdempotencyKeys = loadPendingKeys()

function persistPendingKeys() {
  try { localStorage.setItem(IDEMPOTENCY_STORAGE_KEY, JSON.stringify(Object.fromEntries(pendingIdempotencyKeys))) }
  catch { /* Keep the in-memory key if browser storage is unavailable. */ }
}

async function sha256(value: string | ArrayBuffer): Promise<string> {
  const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : value
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
}

export async function uploadIdempotencyIdentity(knowledgeBaseId: string, file: File): Promise<string> {
  const contentDigest = await sha256(await file.arrayBuffer())
  return `upload:${await sha256(JSON.stringify([
    knowledgeBaseId, file.name, file.type, file.size, file.lastModified, contentDigest,
  ]))}`
}

export class IdempotencyKeyManager {
  async keyFor(identity: string): Promise<string> {
    const stableIdentity = await sha256(identity)
    let key = pendingIdempotencyKeys.get(stableIdentity)
    if (!key) {
      key = newIdempotencyKey()
      pendingIdempotencyKeys.set(stableIdentity, key)
      persistPendingKeys()
    }
    return key
  }

  async complete(identity: string, key: string): Promise<void> {
    const stableIdentity = await sha256(identity)
    if (pendingIdempotencyKeys.get(stableIdentity) === key) {
      pendingIdempotencyKeys.delete(stableIdentity)
      persistPendingKeys()
    }
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${base}${path}`, { ...init, headers })
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as Problem | null
    throw new ApiError(problem ?? {
      type: 'about:blank', title: 'Request failed', status: response.status,
      detail: 'The request could not be completed.', code: 'internal_error', requestId: '', retryable: false, runId: null,
    })
  }
  return response.json() as Promise<T>
}

const json = (method: string, body?: unknown, key?: string): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
  headers: key ? { 'Idempotency-Key': key } : undefined,
})

export const api = {
  knowledgeBases: () => request<PageKnowledgeBase>('/knowledge-bases'),
  createKnowledgeBase: (name: string, description?: string) =>
    request<KnowledgeBase>('/knowledge-bases', json('POST', { name, description })),
  documents: (kbId: string, page = 1, pageSize = 50) =>
    request<PageDocument>(`/knowledge-bases/${encodeURIComponent(kbId)}/documents?page=${page}&pageSize=${pageSize}`),
  document: (id: string) => request<DocumentDetail>(`/documents/${encodeURIComponent(id)}`),
  chunks: (id: string) => request<ChunkTree>(`/documents/${encodeURIComponent(id)}/chunks`),
  upload: async (kbId: string, file: File, idempotencyKey: string) => {
    const data = new FormData()
    data.set('file', file)
    return request<UploadResult | PendingUpload>(
      `/knowledge-bases/${encodeURIComponent(kbId)}/documents`,
      { method: 'POST', body: data, headers: { 'Idempotency-Key': idempotencyKey } },
    )
  },
  process: (id: string, retry: boolean, idempotencyKey: string) =>
    request<ProcessResult>(`/documents/${encodeURIComponent(id)}/${retry ? 'retry' : 'process'}`, json('POST', undefined, idempotencyKey)),
  retrieve: (knowledgeBaseId: string, query: string, documentIds: string[], idempotencyKey: string) =>
    request<RetrievalDebugResult>(
      '/retrieval/debug', json('POST', { knowledgeBaseId, query, documentIds: documentIds.length ? documentIds : undefined }, idempotencyKey),
    ),
  createConversation: (knowledgeBaseId: string) =>
    request<Conversation>('/chat/sessions', json('POST', { knowledgeBaseId })),
  conversation: (id: string) => request<ConversationDetail>(`/chat/sessions/${encodeURIComponent(id)}`),
  sendMessage: (id: string, question: string, idempotencyKey: string) =>
    request<SendMessageResult>(
      `/chat/sessions/${encodeURIComponent(id)}/messages`, json('POST', { question }, idempotencyKey),
    ),
  runs: (page = 1, pageSize = 50, filters: { knowledgeBaseId?: string; kind?: string; status?: string } = {}) => {
    const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) })
    for (const [name, value] of Object.entries(filters)) if (value) params.set(name, value)
    return request<PageRun>(`/runs?${params.toString()}`)
  },
  run: (id: string) => request<RunSnapshot>(`/runs/${encodeURIComponent(id)}`),
  providers: () => request<ProviderStatus[]>('/providers'),
  streamUrl: (id: string) => `${base}/runs/${encodeURIComponent(id)}/events/stream`,
}

export function eventFrom(event: MessageEvent<string>): RunEvent | null {
  try { return JSON.parse(event.data) as RunEvent } catch { return null }
}
