## Why

Day 11 разделил память разговора, задачи и владельца, но агент пока не имеет самостоятельных пользовательских настроек поведения. Day 12 добавляет Profile поверх этой памяти и проверяет, что один агент с неизменными фактами автоматически меняет способ ответа при явном выборе другого профиля, сохраняя компонент пригодным для будущего Android Agent Playground.

## What Changes

- Reusable typed `AgentProfile`, owner-scoped create/edit/read/list/select и durable active binding, независимые от Memory и provider SDK.
- Небольшой pure Profile instructions renderer и композиция с существующими `SimpleAgent`, `AgentConfig`, `LlmClient`, session primitives и Day 11 memory selection; автоматическое применение к каждому Day 12 Send/probe.
- Точный Profile Switch contract: меняется active binding, сохраняются owner/task/session IDs, Short-term/Working/Long-term и memory snapshot.
- Отдельный Day 12 namespace с настоящей моделью памяти; SQLite layout остаётся заменяемой implementation detail, старые дни не мигрируются.
- Controlled Compact Engineer / Mentor comparison на одном immutable memory/transcript snapshot с одинаковым query/model/settings, natural Markdown и side-effect-free probes.
- Независимые selection, actual request assembly, deterministic adherence checks и human observations, без общего quality score и hidden retries.
- Android laboratory UI с настоящим typed profile editor/selector, сравнением, inspector и обычным Send; restore/recovery без replay.
- Tests для domain/storage/lifecycle/concurrency/actual dispatch и Android contracts/UI; live acceptance отдельно от recording-client tests. Day README содержит только подтверждённые результаты.

## Capabilities

### New Capabilities

- `agent-profiles`: самостоятельные typed profiles, ownership, durable selection, revisions, lifecycle и pure instructions projection.
- `profile-personalization-experiment`: Day 12 composition, immutable snapshots, controlled A/B, ordinary Send и независимые observations.
- `profile-personalization-android`: typed editor/selector, comparison, inspector, ordinary Send и recovery UI.

### Modified Capabilities

- `first-agent-conversation`: additive Day 12 contract переиспользования generation/atomic pair primitives при сохранении старых namespaces.
- `learning-days-navigation`: независимый Day 12 destination и сохранение UI state без replay.
- `learning-days-presentation`: карточка и русские подписи Day 12, разделяющие Profile, Memory и виды наблюдений.

## Impact

Backend: новые Profile domain/storage/renderer и Day 12 application service/API; wiring в `app/main.py`. Возможен узкий перенос существующей memory selection/policy из модуля с A–E fixtures без изменения Day 11 semantics. `memory-layers-experiment` и `memory-layers-android` не требуют delta: их поведение остаётся прежним, Day 12 integration описывается новой capability.

Android: существующие Compose/MVVM/Retrofit, `AppContainer`, `MainActivity`, `AppRoot`, каталог, новые scoped DTO/repository/ViewModel/screen/tests. Документация: `day-12-agent-personalization/README.md` и component README при реализации. Новые providers, frontend stack и infrastructure не требуются; SQLite files остаются локальными и не попадают в Git.

Вне scope: RAG, embeddings/vector DB, semantic routing/classification, skills/tools orchestration, multi-agent framework, State Machine, Invariants, generic validation/retry, universal runtime/Prompt DSL, Web frontend, migration старых Days и поля domain/purpose на будущее. Validation-before-commit фиксируется только как constraint последующих Days; `SimpleAgent.run_turn()` ради него сейчас не рефакторится. Этот change создаёт planning artifacts; implementation начинается отдельным запросом.
