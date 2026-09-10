## Why

Day 08 показал рост input/cost при повторной передаче full history и конечность context window. Day 09 впервые меняет context assembly strategy: сравнивает полную историю с rolling summary + fixed raw tail и делает видимыми уменьшение response input, стоимость summarization и сохранение точных фактов.

## What Changes

- Добавить минимальные FullHistoryContextPolicy и RollingSummaryContextPolicy в существующий SimpleAgent; сохранить прежние lifecycle, validation и atomic commit пары. Day 06–08 остаются full-history с прежними provider calls/payload.
- Для Day 09 использовать gpt-4o-mini, strict tail N=4 confirmed messages и синхронное обновление summary до response generation из previous summary + newly eligible raw messages, без current question.
- Сохранять все confirmed raw messages в SQLite; отдельная Day 09 summary table хранит производное состояние с boundary/config version. Synthetic assistant summary существует только в LLM context.
- Добавить изолированный compression-lab API/store/config, exact FULL/COMPRESSED provider counts, signed delta и отдельные operation-level usage/cost/latency/outcomes summary и response phases.
- Добавить явный compare без durable изменений: локальный catch-up summary при необходимости, независимые параллельные FULL/COMPRESSED branches и exact-fact verifier N/3 для видимого учебного сценария.
- Добавить лёгкий Android chat с compact context card и вложенный экран «Статистика и сравнение». Runtime observations/totals принадлежат только CompressionLabViewModel текущего Android process.
- Согласовать отдельные конечные timeout budgets Day 09 и regression coverage, не меняя старые лаборатории.

## Capabilities

### New Capabilities

- `history-compression-experiment`: strict context policy, durable rolling summary, failure boundaries, token/cost accounting, immutable comparison и reproducible factual scenario.
- `history-compression-android`: isolated ViewModel/repository, main/details UX, signed context delta, process-local observations и explicit comparison.

### Modified Capabilities

- `first-agent-conversation`: ограничить full-history/one-generation запреты прежними namespaces; явно разрешить Day 09 context policy и controlled summary/compare phases при общих raw/session гарантиях.
- `learning-days-navigation`: добавить Day 09 и nested Details → Chat → каталог с сохранением состояния и без replay.
- `learning-days-presentation`: добавить русские название/описание Day 09 и понятные обозначения compression trade-off.

## Impact

Backend: agent context extension, narrow ConversationSummaryStore, Day 09 SQLite/config/lifespan/router, operation diagnostics, comparison/verifier; reuse существующих LlmClient, provider TokenCounter и pricing semantics. Android: CompressionLabViewModel, DTO/repository, отдельные preferences/HTTP client, chat/details, каталог и Activity wiring. Документация: day-09-history-compression/README.md и README компонентов при реализации. Нужны backend/JVM/UI regression checks и отдельный live experiment; новые зависимости не планируются.

Non-goals: embeddings/vector retrieval, RAG/MCP, semantic long-term memory, importance ranking, layers/tree summaries, multiple memory tiers, adaptive N, additional trimming, automatic repair/retries, background summarization, tools/planning, Agents SDK, удаление raw source ради compression, generic Context/LabInspector framework, backend runtime accounting/runtime_id и persistent billing journal.
