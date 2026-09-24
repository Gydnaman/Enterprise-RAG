from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from rag_workbench.domain.types import ABSTENTION_TEXT, AnswerDelta


class MockAnswerProvider:
    async def stream(
        self, question: str, evidence: Sequence[dict], history: Sequence[dict]
    ) -> AsyncIterator[AnswerDelta]:
        if not evidence:
            answer = ABSTENTION_TEXT
        else:
            answer = f"演示资料指出：{evidence[0]['snippet']}"
        for offset in range(0, len(answer), 80):
            yield AnswerDelta(answer[offset : offset + 80])
