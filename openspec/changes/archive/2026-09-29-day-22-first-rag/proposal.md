## Why

Day 21 сохранил индекс repository, но ещё не проверял поиск и использование найденных фактов моделью. Day 22 добавляет первый наблюдаемый RAG-запрос и контролируемое сравнение direct/RAG, чтобы различать ошибки поиска, сборки контекста и генерации на одном фиксированном наборе вопросов.

## What Changes

- Переиспользовать pinned persisted Day 21 run без индексации: structure-aware, 226 vectors, query embedding той же конфигурацией, brute-force cosine и fixed Top-5 без threshold.
- Добавить локальный CLI `search`, `ask --mode direct|rag`, `eval`, `report`; показывать источники, scores, chunks, оба ответа и ручной review.
- Использовать одинаковые instructions и generation configuration: существующий client, `gpt-5.6`, reasoning none, output budget 600 tokens; project context является основной переменной.
- Зафиксировать десять repository-specific questions/expectations: пять локальных, три cross-source, один сложный multi-fact и один negative control.
- Сохранить evidence одного полного live eval после offline checks: 10 query embedding calls и по 10 direct/RAG generations, без предварительной semantic настройки на этих вопросах и повторов ради лучшего ответа.
- Разделить вспомогательный `source_path_hit@5`, ручное наличие каждого факта в retrieved context, покрытие фактов ответами и groundedness существенных утверждений RAG.
- Документировать только наблюдения выбранного набора и запуска, без общего вывода «RAG лучше».

## Capabilities

### New Capabilities

- `first-rag-experiment`: наблюдаемый CLI baseline retrieval → context → generation, контролируемая пара direct/RAG, фиксированный вопросник и ручной разбор сохранённого evidence.

### Modified Capabilities

Нет. Контракт Day 21 остаётся самостоятельной индексацией; Day 22 читает её persisted output. Старые agent/API/Android contracts не меняются.

## Impact

- Новые небольшие Day 22 модули и CLI в backend; переиспользование Day 21 loader/embedder и существующего generation runtime без изменения defaults старых дней.
- `day-22-first-rag/README.md` и versioned questions JSON; ссылка в корневом README, команды/setup в backend/scripts README.
- Локальные evidence и manual review в игнорируемом `backend/.local/day22/`; SQLite Day 21 открывается read-only.
- Существующие OpenAI SDK и Python standard library достаточны. Новые сервисы, API endpoints и Android UI не требуются.
- Вне scope: fixed-vs-structure comparison, FAISS/vector DB, hybrid search, reranking, query rewriting, semantic evaluator, RAGAS, MCP и agent orchestration.
