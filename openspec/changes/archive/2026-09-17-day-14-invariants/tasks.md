## 1. Invariant contracts and typed coding policy

- [x] 1.1 Добавить provider-independent rule references, immutable source metadata, violations и passed/violated/unavailable results; проверить unit cases, где missing mandatory check не становится pass, и отсутствие SDK/lab/domain imports в core.
- [x] 1.2 Определить typed CodingPolicy, controlled intents и CodingProposal с architecture/UI/async/confirmation/retry choice без DSL и свободного prose; проверить strict types, domain alternatives и отдельное нарушение каждого из четырёх rules.
- [x] 1.3 Реализовать consistency/request/candidate predicates и trusted guidance/answer/refusal renderers; проверить Working mismatch против soft Long-term preference, три violations conflicting intent, различие request/candidate refusal и отсутствие raw text interpolation.

## 2. Durable sources and candidate adapter

- [x] 2.1 Добавить task policy create/read persistence в isolated Day 14 namespace с immutable versioned record; проверить idempotent installation, запрет replacement, missing/corrupt/unsupported version, rollback и exact reopen без provider calls.
- [x] 2.2 Добавить candidate-generation/parser adapter поверх SimpleAgent.generate/LlmClient с локальным strict parsing; проверить valid incompatible candidate, missing/extra/duplicate fields, неверные types/enums, trailing prose, provider refusal/incomplete/error и максимум один generation call.
- [x] 2.3 Подключить optional trusted invariant section к pure request preparation и actual capture после adapter-specific config; проверить exact recording-delegate equality, неизменный input старого Day 13 без секции и отсутствие diagnostics/expected results в prompt.
- [x] 2.4 Проверить provider independence двумя lightweight test adapters с одинаковым typed candidate и non-coding test predicate; подтвердить одинаковые assessment/gate/refusal без реализации другого агента или изменения coding policy.

## 3. Validated turn and commit recovery

- [x] 3.1 Реализовать bounded coordinator с session guard, captured-history check, injected generation/validation/rendering и единственным atomic pair commit path; проверить accepted pair, guard release при cancellation/error и отсутствие commit до gate.
- [x] 3.2 Реализовать request-conflict и generated-violation terminal paths; проверить 0/1 generation соответственно, точную user/refusal pair и отсутствие raw candidate в runtime history, durable reopen и следующем model input.
- [x] 3.3 Реализовать fail-closed technical paths отдельно от semantic refusals; fault tests должны подтвердить no pair/no invented violations для configuration, parser, unavailable/throwing validator, renderer и provider failures.
- [x] 3.4 Разделить decision и commit outcome, добавить affected-session reconciliation после storage uncertainty; проверить rollback accepted/refusal pairs, durable-write-then-lost-response, refresh cache и блокировку новых turns при failed recovery без automatic replay.

## 4. Day 14 service API and observations

- [x] 4.1 Добавить isolated composition root и lab service с Memory/Profile/State/policy readiness и explicit missing-component setup; проверить cold reads без writes/calls, отсутствие overwrite, partial setup recovery на тех же IDs и сохранение старых namespaces.
- [x] 4.2 Добавить lifecycle New Conversation/New Task и explicit Checkout event operations через существующий resolver/CAS; проверить сохранность/inactive selection policy, initial State новой task, ACTIVE execution applicability и отсутствие transitions из accepted/refused responses.
- [x] 4.3 Добавить backend-owned action catalog и proposal endpoint с current source references; проверить unknown action/extra fields, stale/foreign/inactive references, busy mutations и consistency errors до dispatch без semantic refusal commit.
- [x] 4.4 Сформировать immutable per-attempt receipts и safe technical error envelope; проверить null actual request/candidate при controlled conflict, actual capture/usage при generation, отдельные parsing/assessment/decision/commit statuses и отсутствие секретов/headers.
- [x] 4.5 Выполнить интеграционную матрицу compatible, request conflict, fake candidate violation, internal inconsistency и technical failure; подтвердить exact call counts и неизменность State/Working/Long-term/Profile/policy, кроме ожидаемой Short-term pair.

## 5. Android compact lab

- [x] 5.1 Добавить Day 14 DTO/Repository и подключение в AppContainer; repository tests должны проверить action IDs/source references, not_dispatched refusal и сохранение доступного receipt из technical error response.
- [x] 5.2 Добавить ViewModel с explicit readiness/busy/recovery, setup/lifecycle/events и двумя proposal actions; JVM tests должны подтвердить backend-derived dispatch/commit, no automatic replay, partial setup recovery и no duplicate requests.
- [x] 5.3 Создать compact main/setup/inspector UI с invariants card, краткими summaries, trusted final reply/refusal и отдельной technical error; scoped UI tests должны проверить actions, readiness/State gating, zero-call refusal и rejected-candidate diagnostic label.
- [x] 5.4 Добавить Day 14 destination/card/title и сохранение screen state; проверить Back, rotation/in-flight request, catalog round trip, исторический receipt, узкий экран и независимость старых дней. Existing accessibility tests сохранять; отдельная expanded font-scale проверка нужна только при реальном layout regression или отдельной accessibility задаче.

## 6. Verification documentation and live acceptance

- [x] 6.1 Выполнить scoped backend tests для policy/store/adapter/coordinator/API и затронутых общих primitives; regression exact-payload/call-count/commit checks Day 02–13 должны подтвердить сохранение прежних контрактов без FSM/Profile refactoring.
- [x] 6.2 Запустить Android JVM checks, build и scoped UI checks нового экрана и затронутой navigation; preferred path — PowerShell 7 `scripts/dev.ps1 unit`, `build` и `ui -Test`. При недоступном pwsh/ExecutionPolicy разрешены прямые Gradle commands из `android-app`: `gradlew.bat testDebugUnitTest`, `gradlew.bat assembleDebug` и `gradlew.bat connectedDebugAndroidTest` с фильтром затронутого test class. Подтвердить успешные результаты, переиспользуя работающий emulator и установленный JDK без параллельного Gradle; починка локального PowerShell окружения не входит в Day 14.
- [x] 6.3 Создать краткий `day-14-invariants/README.md` и относительную ссылку в разделе «Задания» корневого README; проверить порядок, отсутствие дубликата, существование target и честный статус ещё не проведённых live checks.
- [x] 6.4 Обновить backend/Android и при необходимости scripts README с setup, boundary guarantees, terminal/recovery semantics и минимальным live flow; проверить команды/ссылки и отсутствие секретов, не дублируя длинные инструкции в Day README.
- [x] 6.5 Подготовить managed backend session; preferred path — `scripts/dev.ps1 backend` и `status`. При недоступном pwsh/ExecutionPolicy разрешён запуск из `backend` в существующем Python-окружении: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`. Проверить readiness/status прямым HTTP `/health` и read-only current при недоступности скрипта, отдельно подтвердить доступность backend с emulator без починки PowerShell tooling; `/health` не подтверждает OpenAI. Затем выполнить один реальный compatible attempt и controlled conflict, зафиксировать actual input, validation, commit и call counts без retries ради успеха. Отмечать live happy path подтверждённым только при фактическом принятом candidate; нарушения/ошибки сохранить как наблюдения.
- [x] 6.6 Зафиксировать фактический live результат в Day README, проверить итоговый scoped diff/структуру и `openspec validate day-14-invariants --strict`; не выполнять commit/push/archive без отдельного соответствующего запроса пользователя.
