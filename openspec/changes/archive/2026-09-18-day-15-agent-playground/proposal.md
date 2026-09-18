## Why

Days 11–14 уже предоставляют Memory, Profile, deterministic Task State Machine и generate–validate–commit boundary, но пользователь работает с отдельными лабораториями. Day 15 объединяет их в Android Agent Playground и доказывает controlled red paths: запрещённые скачки отклоняются, а разрешённые возвраты по графу явно применяются пользователем с последующим продолжением задачи.

## What Changes

- Добавить небольшой reusable integration coordinator поверх существующих request preparation, candidate generation и validated-turn primitives; lifecycle service отдельно использует существующий FSM resolver и CAS. Send никогда не применяет workflow event, lifecycle operations никогда не вызывают LLM.
- Добавить только для Day 15 versioned definition `checkout-v2`: сохранить пять узлов и четыре forward edges, добавить REQUIREMENTS_REVISION_REQUIRED из согласования плана к требованиям и VALIDATION_FAILED из проверки к реализации. Engine и `checkout-v1` Days 13–14 остаются прежними; recovery не является invalid transition или откатом conversation.
- Добавить изолированную Coding Agent composition и reviewed создание Checkout task с Compact Engineer/Mentor и четырьмя существующими typed CodingPolicy settings: architecture, UI toolkit, async model и payment confirmation. Policy immutable для task; смена Profile влияет только на следующие Send.
- Обеспечить coherent initial Working facts, сохранение подтверждённой конфигурации при partial setup и восстановление на тех же IDs без defaults/reset/replay.
- Ввести отдельный разговорный candidate-контракт с bounded validation структурированных coding decisions. Свободный текст не считается полностью semantic-safe; строгий bounded CodingProposal Day 14 сохраняет прежний контракт.
- Создать user-oriented main: Task, stage/step, next action, Profile, compact policy, chat, contextual lifecycle actions, Pause/Resume и отдельный operation result. Done оставляет conversation read-only.
- Добавить Inspector с summary, раскрываемыми semantic sections и отдельным Raw Debug; historical receipts не пересобираются из current state.
- Проверить forward/recovery/off-graph paths, неизменность State после Send, configurable policies, persistence/reconciliation и независимость старых labs. Короткий live показывает один forbidden skip, Pause/Resume, VALIDATION_FAILED и повторный forward path до Done; оба recovery edges и оба forbidden skips покрываются offline. Добавить Day README и ссылку в корневом README при реализации.

## Capabilities

### New Capabilities

- `agent-runtime-integration`: reusable source composition, bounded Send acceptance, отдельное application-owned lifecycle application, immutable receipts и recovery без replay.
- `agent-playground-experiment`: конкретная Coding Agent configuration, immutable task policy, reviewed setup, natural conversation contract и интеграционный acceptance Day 15.
- `agent-playground-android`: Playground main/setup, contextual controls, chat semantics, Inspector/Raw Debug и client recovery.

### Modified Capabilities

- `learning-days-navigation`: добавить независимый Day 15 destination, внутреннюю навигацию и сохранение состояния без replay.
- `learning-days-presentation`: добавить русское представление Day 15 и понятные labels lifecycle/bounded evidence.

## Impact

- Backend: новая Playground composition/API и отдельный durable namespace; reuse `MemoryStore`, Profile store, `TaskStateDefinition`/resolver/store, `prepare_agent_request`, `LlmClient`, `run_validated_turn`, conversation commit и capture. Минимальное выделение общей orchestration допускается без миграции старых labs.
- Android: новый Repository/ViewModel, main/setup/Inspector/Raw Debug, wiring в AppContainer, MainActivity и каталог; reuse подходящих chat components без переноса session-only ChatViewModel.
- Verification: targeted backend/JVM/UI regressions и один человечески понятный live workflow; README компонентов содержит технические инструкции, Day README — фактические результаты.
- Day 14 durable policy и bounded proposal contracts, FSM engine и данные Days 11–14 не меняются. Новые runtime зависимости и migration старых namespaces не требуются.
- Вне scope: generic Back/goToState, arbitrary next_state, rollback stack/history rewind/undo conversation, semantic auto-detection failure, automatic model-selected recovery, semantic verifier произвольного кода/prose, policy hot-editing, DSL/config language, dynamic workflows, автоматические transitions, дополнительные agents, tools framework, multi-agent orchestration, Web UI, operation journal и distributed locking.
