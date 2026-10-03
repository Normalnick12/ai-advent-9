## Why

Day 22 показал неподдержанные утверждения при непустом retrieved context; Day 23 rewrite/filter не улучшил fact coverage и дал регрессию Q05. Day 24 изолирует контракт ответа: пользователь и runtime должны видеть проверяемые источники и точные цитаты, а недостаточный context должен приводить к явному abstention.

## What Changes

- Изолированный CLI Day 24 повторяет original-query cosine Top-5 из frozen Day 22 vectors и pinned Day 21 index, без новых embeddings или изменения retrieval.
- Фиксированный best-score gate 0.50 возвращает deterministic insufficient_context без generation либо передаёт все пять chunks Structured Outputs generation.
- Единый response answered/insufficient_context; обязательные sources/citations у answered, корректно пустые массивы у abstention. Runtime отдельно проверяет provenance и literal quotes, сохраняя failures без repair/retry.
- Локальное evidence различает runtime и model abstention, сохраняет actual request, raw output, validation и отдельный manual semantic review. CLI предоставляет подробный report и компактный --video.
- Focused offline tests и один frozen live experiment Q01–Q10; документация явно ограничивает выводы этим run.

## Capabilities

### New Capabilities

- `grounded-rag-experiment`: Frozen retrieval replay, relevance gate, structured response, deterministic provenance/citation validation, manual review и CLI evidence Day 24.

### Modified Capabilities

Нет. Контракты и результаты Days 21–23 остаются самостоятельными экспериментами; их helpers переиспользуются без изменения поведения.

## Impact

Новый небольшой слой `backend/app/grounded_rag/`, CLI `backend/scripts/day24_rag.py`, focused backend tests, `day-24-grounded-rag/README.md` и ссылка в корневом README; команды/контракт в scripts/backend README. Используются существующие Python environment, Responses client и локальные ignored SQLite/evidence; новых сервисов и зависимостей не требуется. Scope исключает indexing, rewrite, reranker, hybrid retrieval, RAGAS/LLM judge, MCP, Android UI и generic citation framework.
