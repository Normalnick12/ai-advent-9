## Why

Day 06–10 отделили Agent, Session и выбор контекста, но ещё не моделируют независимые conversation-, task- и owner-scoped memory. Day 11 должен на одном контролируемом сценарии показать: `stored state != active context != model output`, сохраняя инфраструктуру предыдущих дней.

## What Changes

- Добавить явные Short-term (transcript session), Working (structured task state) и Long-term (durable owner state) с независимыми session_id, task_id и memory_owner_id.
- Хранить три слоя и durable current identity binding в отдельной SQLite-базе Day 11. New Conversation и New Task создают новые identities, сохраняя прежние данные inactive; Clear Long-term очищает только Long-term. Restart восстанавливает память и binding без replay.
- Подключить MemoryExperimentService и MemoryContextPolicy к существующим SimpleAgent, AgentSession/Manager, ConversationStore и LlmClient; не создавать второй Agent stack.
- Выполнять routing, typed set/remove, validation, lifecycle и context selection детерминированно. Добавить ровно одно правило: Working current_architecture исключает Long-term preferred_architecture из effective context, не изменяя stored preference.
- Провести side-effect-free verification A–E с exact markers ORION-17 / RC-42 / Сбой-47 и раздельными результатами «доступно в assembled input» и «использовано моделью».
- Добавить отдельный компактный Android Day 11: три memory cards, шаг эксперимента, latest response, раскрываемый inspector и runtime dashboard. Сохранение observations/results не требуется.
- Сохранить прежние API, настройки, provider call counts и semantics Day 02–10.

## Capabilities

### New Capabilities

- `memory-layers-experiment`: ownership, deterministic writes, durable lifecycle, assembly/precedence, A–E verification и отдельная restart acceptance.
- `memory-layers-android`: Day 11 scenario UI, state/inspector, раздельные метрики, read-only restore и recovery без replay.

### Modified Capabilities

- `first-agent-conversation`: подключение Day 11 к общим Agent/session primitives при сохранении контрактов предыдущих дней.
- `learning-days-navigation`: карточка Day 11 и переходы без автоматических mutations/provider calls.
- `learning-days-presentation`: русская идентичность Day 11 и понятное представление трёх слоёв и двух независимых результатов проверки.

## Impact

Backend: новый изолированный Memory Layers service/API/store/context modules, точечная интеграция в FastAPI lifespan; переиспользование existing SQLite conversation storage и Agent generation lifecycle. Android: отдельные DTO/repository/ViewModel/screen и подключение через существующий composition root, без новых DI frameworks. Документация реализации: day-11-memory-layers/README.md и необходимые дополнения component README; здесь создаются только planning artifacts.

Не требуются новые внешние сервисы или зависимости. Не входят RAG, embeddings/vector DB/retrieval, LLM routing/extraction, promotion, scoring/forgetting, multi-agent memory, Summary/Window comparisons, Branching, generic memory/conflict framework, State Machine, invariants engine и planning framework. Delete/reset и повторная активация inactive данных не входят в обязательный scope.
