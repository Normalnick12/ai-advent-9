## Why

После Day 07 агент надёжно сохраняет диалог, но не показывает цену повторной передачи полной истории и предел context window. Day 08 делает эти последствия измеримыми на коротком, длинном и реально переполненном контексте, не оптимизируя и не сокращая историю.

## What Changes

- Добавить отдельную лабораторию «Работа с токенами» с фиксированной `gpt-4o-mini`, context window 128000 и тем же `SimpleAgent` algorithm. Day 06/07 сохраняют `gpt-5.6` и прежнее поведение.
- Изолировать Day 08 через отдельные API namespace, session manager и SQLite-файл с существующей schema; не разрешать продолжение или удаление чужих sessions через другой Agent namespace.
- Добавить небольшой async `TokenCounter` и OpenAI adapter для официального provider preflight, без tiktoken. Измерять current message и непустую saved history как самостоятельные structured requests без instructions, а full preflight — как exact generation context с instructions. Использовать один immutable snapshot; пустая history даёт 0 без count call. Эти числа неаддитивны и не складываются в full input.
- Сохранять доступный actual provider usage в нейтральном LLM result; объединять outcome и diagnostics текущей попытки в `AgentTurnResult`. Стоимость вычислять после generation по actual usage и фиксированным тарифам, с nullable неизвестными значениями.
- Обычный Send автоматически выполняет preflight и максимум одну generation. Отдельный overflow workflow подготавливает видимый deterministic payload, подтверждает превышение через count API и только после явного действия выполняет один настоящий provider request с disabled truncation и zero retries.
- Добавить отдельный `TokenLabViewModel`, небольшие общие stateless chat components, diagnostics и runtime-only таблицу попыток. Android получает counts/cost с backend, не отправляет history/config.
- Сохранить atomic durable user/assistant pairs, отсутствие commit при failed/preflight/overflow outcomes и пригодность session после подтверждённого overflow. Не менять SQLite schema и Day 05 benchmark semantics/results.

## Capabilities

### New Capabilities

- `token-lab-experiment`: фиксированная конфигурация, изоляция sessions, provider counting/usage, pricing, short/long/overflow lifecycle и экспериментальные гарантии.
- `token-lab-android`: отдельный chat state, diagnostics, runtime observations, явное разрешение overflow и восстановление identity без historical metrics.

### Modified Capabilities

- `first-agent-conversation`: уточнить границу общего алгоритма и Day 06/07 namespace; разрешить отдельному Day 08 instance diagnostics calls, сохранив старые API и generation/commit guarantees.
- `learning-days-navigation`: включить Day 08 в каталог и независимое сохранение состояния при навигации.
- `learning-days-presentation`: русские название, описание и понятные подписи новой лаборатории.

## Impact

Затронуты backend Agent/LLM contracts, OpenAI adapter, composition root и новые Day 08 routes/diagnostics/pricing; Android navigation/AppContainer и stateless chat presentation. OpenAI SDK уже содержит input-token counting; новой tokenizer dependency нет. Добавляется отдельный локальный SQLite-файл с прежними таблицами, без migration или usage journal. Документация Day 08 и компонентов обновляется при apply; исторические результаты Day 05 не переписываются. Публичные Day 02–07 contracts не ломаются.

Non-goals: summarization, compression, sliding window, trimming/cut, automatic truncation, embeddings/vector/semantic memory, RAG/MCP, planning/tools, automatic model switching, Agents SDK, persistent billing/usage journal, analytics framework и cache optimization experiment.
