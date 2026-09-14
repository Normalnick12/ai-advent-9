## 1. Domain contracts and isolated storage

- [x] 1.1 Добавить Day 11 memory models, independent owner/task/session identities, allowlisted string fields и explicit set/remove contracts; проверить unit-тестами invalid layer/key/type/null/extra fields, no-op remove и отсутствие partial mutations.
- [x] 1.2 Добавить отдельную Day 11 SQLite schema с raw sessions/messages, Working, Long-term, session-to-task association и current binding; проверить temporary-file round trips, ownership constraints и отсутствие изменений старых databases.
- [x] 1.3 Подключить WorkingMemoryStore/LongTermMemoryStore к общей connection с существующим ConversationStore; проверить независимость записи слоёв и сохранение existing atomic pair/schema validation tests.

## 2. Durable lifecycle and current identities

- [x] 2.1 Реализовать explicit idempotent Initialize и read current/not_initialized без implicit writes; проверить одинаковые identities после повторного Initialize и нулевые provider calls при read/startup.
- [x] 2.2 Реализовать atomic New Conversation/New Task через transaction-aware storage operations; проверить новые current IDs, пустые новые scopes, unchanged Long-term и exact сохранность inactive task/session rows после reopen.
- [x] 2.3 Реализовать Clear Long-term и согласовать runtime session cache с post-commit binding без manager.delete/close для New; проверить unchanged Working/Short/IDs, inactive target rejection и загрузку новой session через existing manager.
- [x] 2.4 Добавить failure-injection тесты lifecycle до COMMIT и read reconciliation после committed transition с потерянным HTTP ответом; проверить rollback всех новых rows/binding и отсутствие phantom current sessions в cache.
- [x] 2.5 Реализовать strict restore и stable snapshot fingerprint identities/revision/structured states/raw history; проверить exact nonempty restore новым store/manager instance, safe corruption errors и отсутствие busy/pending/provider replay.

## 3. Context builder and shared Agent integration

- [x] 3.1 Создать pure builder/immutable MemoryContextPolicy adapter для selected Long-term + Working + active Full History; проверить exact roles/text/order, single current message, empty blocks и отсутствие inactive/audit/verification sources.
- [x] 3.2 Добавить только правило Working current_architecture overrides Long-term preferred_architecture; проверить A/B fallback, unchanged stored MVVM и отсутствие исключённого значения через diagnostics в provider input.
- [x] 3.3 Реализовать MemoryExperimentService ordinary Send через SimpleAgent.run_turn с реальным AgentSession; проверить completed pair, failed/refused/incomplete/cancelled outcomes без commit и сохранность ранее explicit memory writes.
- [x] 3.4 Подключить Day 11 AgentConfig, existing LlmClient и owner guard/stale snapshot checks; проверить не более одной generation на Send, ноль maintenance/count calls, отсутствие SQL transaction во время provider await и rejection competing mutations.

## 4. Side-effect-free controlled verification

- [x] 4.1 Добавить exact seed fixture, explicit Long/Working setup и immutable A–E query/output schema/oracle по design; проверить ORION-17/RC-42/Сбой-47, отсутствие expected values/stage labels в instructions/query/schema и пригодность повторной explicit подготовки после E.
- [x] 4.2 Реализовать verification через SimpleAgent.generate без commit; проверить identity/revision/слои до и после success/failure/cancellation, отсутствие previous probe outputs в новых requests и максимум один call на probe.
- [x] 4.3 Реализовать actual stage preconditions и runtime before/after lifecycle observations без state-machine framework; проверить scenario_not_applicable, continuation по actual state после потери runtime progress и отсутствие ложных scores.
- [x] 4.4 Добавить раздельные per-field input availability/absence/conflict и output exact/null checks; проверить случай correct MVI input + wrong MVVM response, malformed/extra-field output, failed generation и незасчитываемый free next_step.
- [x] 4.5 Собрать recording-fake A–E integration test: один committed seed, explicit writes/remove/lifecycle и пять probes; проверить expected fields каждого этапа, retained inactive rows и ровно 6 generation / 0 maintenance/count calls.

## 5. API and observability contracts

- [x] 5.1 Добавить отдельный memory-layers router/DTO и lifespan wiring для current/catalog/initialize/mutations/Send/lifecycle/verify; проверить strict API contracts, safe errors, namespace isolation и нулевые provider calls для deterministic endpoints.
- [x] 5.2 Вернуть compact current cards data, inactive refs/counts и immutable observation/inspector snapshot с selected/excluded reasons и actual response; проверить correspondence actual provider payload, отсутствие credentials/headers и отсутствие observation tables.
- [x] 5.3 Реализовать busy/stale/not_initialized/recovery responses без automatic retries; проверить lost response reconciliation read и отсутствие silent owner/session recreation.

## 6. Android laboratory and navigation

- [x] 6.1 Добавить отдельные DTO/API/repository и зависимости в существующий AppContainer; проверить JVM-тестами field/identity/snapshot validation, backend binding как source of truth и отсутствие client-supplied history/settings.
- [x] 6.2 Добавить ViewModel explicit setup/actions/A–E, read restore и unknown-outcome recovery; проверить JVM-тестами нулевой replay, stale snapshot handling, потерю runtime results без потери memory и independent input/output metrics.
- [x] 6.3 Создать compact Short/Working/Long cards, current step, latest response и A–E dashboard с понятными Russian labels; проверить targeted Compose tests на actions, exact markers, unknown/null/error и correct context + wrong output.
- [x] 6.4 Добавить раскрываемый inspector stored/selected/excluded/request/response и previous-snapshot labels; проверить targeted UI-тестом stored/selected/excluded, override reason, request/response, previous snapshot и Back/navigation behavior. Dedicated increased-font/font-scale smoke не требуется без соответствующей задачи или реального layout regression; существующие accessibility tests не удалять.
- [x] 6.5 Добавить карточку «День 11 — Модель памяти агента», порядок 02–11 и сохранение Day 11 UI в процессе; проверить navigation tests, Activity recreation без replay и неизменность состояния других дней.

## 7. Regression and implementation validation

- [x] 7.1 Запустить новые backend memory tests и существующие Agent/session/conversation store, payload, compression/context strategies regression tests по backend README; зафиксировать pass/fail и исправить выявленные регрессии до live acceptance.
- [x] 7.2 Выполнить затронутые JVM tests, build и targeted Day 11/navigation UI tests, расширив UI-прогон при связанных изменениях навигации; предпочитать PowerShell 7 scripts/dev.ps1, но при недоступных pwsh/ExecutionPolicy использовать прямые Gradle commands проекта без конкурирующих сборок в том же checkout. Исправление PowerShell/dev tooling не входит в Day 11; зафиксировать результаты без повторения неизменившихся успешных проверок.
- [x] 7.3 Проверить schema/spec coherence командой openspec validate day-11-memory-layers --strict, синтаксис изменённых implementation files и git diff/status; подтвердить scoped changes и отсутствие secrets/local database в отслеживаемых файлах.

## 8. Live acceptance and documentation

- [x] 8.1 Подготовить отдельную управляемую backend terminal session: предпочитать scripts/dev.ps1 backend; при недоступных pwsh/ExecutionPolicy использовать из backend команду python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload в существующем Python-окружении проекта. Проверить готовность через scripts/dev.ps1 status либо напрямую /health при fallback и отдельно доступ backend с переиспользуемого эмулятора; зафиксировать готовность отдельно от OpenAI/live результатов, без автоматических paid calls и без починки PowerShell/dev tooling.
- [x] 8.2 Провести один explicit live A–E проход на заданных markers: один seed до structured writes и пять probes, включив restart acceptance 8.3 на непустом A-state до перехода к B; записать фактические assembled-source checks и model output checks отдельно, ошибки модели не подменять storage failures и не считать fake результаты live evidence.
- [x] 8.3 На непустом A-state выполнить отдельную restart acceptance: сохранить before snapshot, остановить/запустить backend, read current без generation; проверить same owner/task/session IDs, exact три слоя и отсутствие replay, не требуя persistence dashboard.
- [x] 8.4 Создать краткий day-11-memory-layers/README.md по шаблону проекта и обновить необходимые backend/Android docs; проверить, что Day README содержит только подтверждённые observations либо честное указание непроведённых проверок, а настройка/commands находятся в component README.
