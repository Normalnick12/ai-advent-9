"""Independent Day 33 FastAPI app. Run directly with Uvicorn on loopback."""
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.document_indexing.embedding import OpenAIEmbedder
from app.openai_responses_llm_client import OpenAIResponsesLlmClient
from .models import SupportFailure, SupportRequest
from .rag import build_async
from .service import SupportService

QUESTION = 'Не могу войти в аккаунт. Почему и что делать?'
EXAMPLES = {tid: dict(summary=title, value=dict(ticket_id=tid, question=QUESTION)) for tid, title in (
    ('T-101', '1. Временная блокировка'), ('T-102', '2. Истёкший код'),
    ('T-103', '3. Недостаточно сведений'), ('T-999', '4. Тикет не найден'))}


def create_app(*, embedder_factory=OpenAIEmbedder, client_factory=OpenAIResponsesLlmClient, ticket_reader=None):
    @asynccontextmanager
    async def lifespan(app):
        try:
            faq = await build_async(embedder_factory)
        except Exception:
            raise RuntimeError('day33_faq_startup_failed; check local FAQ and OpenAI configuration') from None
        client = client_factory()
        try:
            options = {} if ticket_reader is None else dict(ticket_reader=ticket_reader)
            app.state.support = SupportService(faq, client, embedder_factory, **options)
            yield
        finally:
            await client.close()

    app = FastAPI(title='DemoStore — поддержка пользователей', version='1.0.0', lifespan=lifespan,
        description='Вымышленные данные, без пользовательской аутентификации. '
                    'Исторический UTC-снимок 16 октября 2026; текущее состояние аккаунтов не проверяется. '
                    'Локальный API. Acceptance-проверки: T-101 → T-102 → T-103 → T-999.')

    @app.exception_handler(SupportFailure)
    async def failure_handler(request: Request, error: SupportFailure):
        code = 404 if error.code == 'ticket_not_found' else 503 if error.code == 'mcp_unavailable' else 502
        category = ('missing_ticket' if code == 404 else
                    'semantic_error' if error.detail in {'unsupported_cause', 'diagnosis_status_mismatch',
                                                        'unknown_requires_clarification'} else
                    'validation' if error.code == 'answer_validation_failed' else 'infrastructure')
        return JSONResponse(status_code=code, content=dict(error=error.code, category=category,
                            detail=error.detail, trace=error.trace))

    @app.get('/health')
    async def health():
        faq = app.state.support.faq
        return dict(status='ready', faq_fingerprint=faq.index.provenance['fingerprint'],
                    corpus=faq.startup, openai_generation_checked=False, mcp_checked=False)

    @app.post('/support/answer', summary='Ответить по выбранному тикету', responses={
        404: dict(description='Тикет не найден; query embeddings и генерация не запускались'),
        502: dict(description='Ошибка retrieval, генерации или валидации ответа'),
        503: dict(description='Ошибка MCP')})
    async def answer(request: SupportRequest = Body(openapi_examples=EXAMPLES)) -> dict:
        return await app.state.support.answer(request)

    @app.get('/support/sources/{doc_id}', response_class=PlainTextResponse, summary='Открыть источник FAQ')
    async def source(doc_id: str):
        faq = app.state.support.faq
        doc = faq.documents.get(doc_id)
        if doc is None:
            return PlainTextResponse('source_not_found', status_code=404)
        lines = '\n'.join(f'{i}: {line}' for i, line in enumerate(doc['text'].splitlines(), 1))
        return f"{doc['source']}\nFAQ snapshot: {faq.index.provenance['fingerprint']}\n\n{lines}\n"

    return app


app = create_app()
