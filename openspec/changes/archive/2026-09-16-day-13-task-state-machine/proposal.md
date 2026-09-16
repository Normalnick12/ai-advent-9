## Why

После Day 11–12 агент хранит факты задачи и настройки поведения, но не имеет самостоятельной формальной позиции в workflow. Day 13 добавляет durable task-scoped FSM, чтобы pause/resume и продолжение после смены conversation опирались на Working + State, а не на старый transcript или догадки LLM.

## What Changes

- Добавить независимые TaskState, versioned machine definition, deterministic transition resolver, Pause/Resume, revision/CAS и layout-independent store с SQLite adapter.
- Использовать canonical node + ACTIVE/PAUSED; phase, step, expected_action, terminal flag и allowed events выводить из definition. Checkout проходит planning requirements/approval, execution, validation и done только через explicit events, включая VALIDATION_CONFIRMED как подтверждение пользователя/application.
- Разрешить ordinary conversation при PAUSED, блокируя workflow events. Send не меняет State; New Conversation сохраняет task/state/profile, New Task получает initial State.
- Подключить State отдельной authoritative workflow section рядом с Profile instructions и Memory data через маленький reusable request preparation layer, без второго Agent stack.
- Добавить isolated Day 13 API/Android lab, actual LlmClient capture и раздельные storage/selection/assembly/model-adherence observations.
- Проверить transition matrix, pause всех non-terminal nodes, durability, lifecycle и controlled State influence offline. Основной live flow обязательно создаёт настоящий execution transcript S0 перед Pause и использует две New Conversation: первая исключает S0, вторая — status answer перед Resume и «Продолжим». Успешный flow требует ровно три generation calls; setup/events/lifecycle/read — ноль provider calls.
- Хранить current State + revision без durable transition history. Три SQLite-файла допустимы только как Day 13 adapter layout; incomplete setup явно блокирует dispatch/events и восстанавливается без hidden replay.

## Capabilities

### New Capabilities

- `task-state-machine`: provider-independent task-scoped FSM, immutable snapshots, definitions, events, pause/resume, durable CAS и pure renderer.
- `task-state-experiment`: Checkout workflow, composition Memory/Profile/State, isolated lifecycle/readiness, actual request evidence, controlled verification и live continuation без старых conversations.
- `task-state-android`: laboratory dashboard, backend-authoritative allowed events, paused conversation, inspector и recovery.

### Modified Capabilities

- `first-agent-conversation`: additive Day 13 composition через existing generation/commit primitives с сохранением Day 02–12 contracts.
- `learning-days-navigation`: отдельный Day 13 destination, сохранение runtime UI state без replay и изоляция старых дней.
- `learning-days-presentation`: карточка Day 13 и ясное различение Memory, Profile, Task State, pause и observations.

## Impact

При последующей реализации затрагиваются backend domain/store/composition/API и composition root, Android Repository/ViewModel/Compose/navigation, scoped tests, новый `day-13-task-state-machine/README.md` и ссылка на него в корневом README. Переиспользуются SimpleAgent, AgentSession/Manager, ContextPolicy, Memory selection, Profile subsystem/renderer и LlmClient; нейтрализация capture сохраняет прежние payloads. Day 11/12 data не мигрируются, их semantics не меняются; новые внешние infrastructure dependencies не требуются.

Invariants, semantic Validator, retries, автоматические transitions из ответов, dynamic planning, workflow DSL/DAG, event sourcing, общая conversation/state transaction и integrated Playground не входят в change. Текущий этап создаёт только planning artifacts; implementation начинается отдельным запросом.
