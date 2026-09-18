## 1. Typed Coding configuration and conversation contract

- [x] 1.1 Добавить strict Day 15 task configuration и backend catalog: Checkout/workflow, Compact Engineer/Mentor и четыре existing CodingPolicy fields; проверить parameterized tests всех supported values и rejection extra fields, неверных types, retry_mode policy setting и arbitrary prompt до writes.
- [x] 1.2 Добавить отдельный versioned conversation candidate answer + four typed decisions и strict parser; проверить missing/extra/duplicate keys, blank/oversized answer, enum/boolean errors и structurally valid policy-incompatible values.
- [x] 1.3 Подключить существующие coding predicates к новому candidate, при необходимости выделив общий four-field type без изменения Day 14 proposal shape; проверить compatible/incompatible values, exact payment=false semantics и прежние parser/render tests Day 14.
- [x] 1.4 Добавить conversation candidate adapter и trusted answer/refusal renderers с application-owned bounded coverage; проверить fake provider success/refusal/parser errors, отсутствие rejected prose в refusal и отсутствие semantic-safe claim при matching decisions с contradictory prose.

- [x] 1.5 Добавить отдельную Day 15 definition checkout-v2: прежние пять узлов/metadata и четыре forward edges плюс REQUIREMENTS_REVISION_REQUIRED (PLANNING_APPROVAL -> PLANNING_REQUIREMENTS) и VALIDATION_FAILED (VALIDATION_CHECK -> EXECUTION_IMPLEMENT); переиспользовать неизменённые TaskStateDefinition/resolver/allowed_events/CAS/PauseResume и сохранить checkout-v1 Days 13–14.

## 2. Reusable Send and lifecycle integration

- [x] 2.1 Выделить небольшой Send coordinator с injected source/preparation/policy/candidate dependencies и reuse prepare_agent_request/run_validated_turn/SimpleAgent.generate; проверить dependency test без coding/checkout/lab/OpenAI SDK imports и отсутствие run_turn bypass.
- [x] 2.2 Реализовать coherent source resolution и общий single-worker guard для Send/source mutations/events/setup; проверить stale task/session/memory/Profile/binding/State/policy references, missing/corrupt sources, consistency error и busy конкуренцию до dispatch.
- [x] 2.3 Сохранить distinct Send outcomes и atomic pair semantics; проверить accepted pair, candidate refusal pair, optional trusted-intent zero-call refusal, natural-query precheck not applicable, checker/render/provider failures, cancellation и no rejected candidate in next input.
- [x] 2.4 Добавить lifecycle service поверх существующих resolver/CAS с injected trusted edge metadata и typed results forward_applied/recovery_applied/rejected, отдельно Pause/Resume и stale/technical outcomes; проверить exact State-only mutation, no direct next_state, ноль provider calls без LlmClient dependency, unchanged conversation и доступность после recovery.
- [x] 2.5 Добавить immutable Send/lifecycle receipts, actual capture, confirmed pair association и persistence reconciliation helper; проверить before/event/after/revisions/next action, различие forward/recovery/rejection, exact delegate arguments, no fabricated request при no dispatch, историчность после source changes и lost commit/recovery acknowledgement без replay.

## 3. Durable reviewed setup and task ownership

- [x] 3.1 Создать отдельный Playground configuration/setup store для immutable reviewed choices и закреплённого machine_id=checkout-v2, reserved identities, expected prior binding и pending/ready; проверить reopen, unsupported/corrupt records, один pending setup и отсутствие domain creation при current read.
- [x] 3.2 Добавить узкий idempotent Memory creation helper с reserved identities и прежними defaults старых callers; проверить atomic binding/session creation, повторное подтверждение exact IDs, stale conflict и existing Memory lifecycle regressions.
- [x] 3.3 Реализовать reviewed create-task/complete-setup orchestration с Working.current_architecture из выбранной policy, owner-scoped presets, checkout-v2 State и immutable policy; проверить default и alternative configurations, ноль provider calls и отсутствие фиктивной зависимости от release_marker.
- [x] 3.4 Защитить partial setup от всех меж-store failures, включая до Memory creation, после binding и после ready write; fault-injection/restart tests должны подтвердить те же IDs/choices, отсутствие defaults/overwrite, explicit completion и no duplicate task после lost response.
- [x] 3.5 Реализовать Profile selector и New Conversation/New Task semantics в отдельном namespace; проверить, что Profile switch меняет только binding, New Conversation сохраняет task sources и исключает старый transcript, а Task B имеет собственную policy без изменения A.

## 4. Playground backend API and application wiring

- [x] 4.1 Подключить Coding composition с checkout-v2, adapters и отдельные storage paths в backend lifespan; проверить path isolation, resource close и отсутствие изменений данных Days 11–14 при startup/shutdown.
- [x] 4.2 Добавить strict catalog/current/create-task/complete-setup/send/events/select-profile/new-conversation API с current refs и typed outcomes; HTTP tests должны различать expected lifecycle rejection, stale/configuration errors, technical Send receipt и unknown transport outcome.
- [x] 4.3 Реализовать backend can_send/readiness, paused clarification и terminal read-only без новой FSM; проверить Send на каждом nonterminal этапе/PAUSED, запрет Send из DONE и no state/revision changes при любом Send outcome.
- [x] 4.4 Добавить trusted catalog labels/edge classification для normal recovery controls и отдельные educational metadata для двух настоящих invalid events; проверить единую events boundary, recovery только из allowed_events, exact unchanged sources при rejection и возможность продолжения после recovery/rejection.

## 5. Android data and state management

- [x] 5.1 Добавить Playground DTO/API/Repository и wiring AppContainer/MainActivity; JVM tests должны проверять refs, декодирование forward/recovery/expected rejection/technical receipts и согласованность actual dispatch/count/commit без fallback replay.
- [x] 5.2 Добавить отдельный PlaygroundViewModel для read-only restore, committed transcript, draft/pending input, operation guard и recovery; JVM tests должны подтвердить duplicate-tap protection, lost-response reconciliation, отсутствие implicit setup и блокировку writes до recovery.
- [x] 5.3 Добавить reviewed configuration draft и explicit create/complete-setup/Profile/New Conversation operations; JVM tests должны подтвердить cancel без writes, восстановление nondefault pending choices, same-ID completion и source-preserving Profile switch.
- [x] 5.4 Добавить runtime receipt map до 50 attempts, pair association и selected Inspector state; проверить историчность после Profile/State/conversation changes, no fabricated association для unknown commit и unavailable после eviction/process death.

## 6. Playground screens and explanation UI

- [x] 6.1 Реализовать task-oriented main с stage/step/next action, Profile, compact policy и настоящим chat; переиспользовать ChatBubble/подходящий composer без session-only ChatViewModel; UI test должен различать committed answer/refusal, pending input и technical operation error.
- [x] 6.2 Реализовать единый reviewed setup с четырьмя typed policy controls и Profile selector; UI test должен подтвердить review/cancel/confirm, read-only policy текущей task и explicit completion partial setup вместо технических fixture buttons.
- [x] 6.3 Реализовать contextual allowed-events controls с «Уточнить требования»/«Проверка не пройдена», отдельные educational checks и удерживаемую lifecycle result card; UI tests должны подтвердить normal recovery без error banner/synthetic pair/очистки chat, before/event/after/next action, updated recovered actions и оба backend rejection.
- [x] 6.4 Реализовать Pause/Resume и DONE presentation; UI tests должны подтвердить paused clarification composer, busy отдельно от Pause, сохранение узла и read-only terminal chat с доступным New Task.
- [x] 6.5 Реализовать pure Inspector summary mapping и semantic expandable sections из selected immutable receipt; JVM/UI tests должны различать Forward applied / Recovery applied / Forbidden transition rejected с before/event/after/revisions и Provider not required, а также bounded coverage, Current/Used in this turn, not applicable/not attempted/not required/unavailable/failed/unknown и acceptance отдельно от commit.
- [x] 6.6 Реализовать отдельный Raw Debug с exact request/config/candidates/provider/violations/receipt и diagnostic-only labels; проверить correspondence выбранному receipt, отсутствие выдуманных actual messages при no dispatch и Back в тот же Inspector.
- [x] 6.7 Добавить Day 15 catalog destination и русские labels, сохранить drafts/scroll/sections/attempt при navigation/rotation; root navigation и narrow/large-font/IME UI tests должны подтвердить доступность controls, отсутствие replay и независимость старых Days.

## 7. Cross-component verification and live acceptance

- [x] 7.1 Выполнить integrated backend acceptance через production API с recording client: forward workflow, оба forbidden skips, Pause/Resume, Send с completion/failure/recovery prose без State mutation, actual four-source request, gate/commit и cold restore; подтвердить exact snapshots/counts, включая default/alternative policies.
- [x] 7.2 Выполнить targeted backend regressions Memory/Profile/FSM/invariants и dependency/provider-substitution tests; проверить прежний checkout-v1 graph/allowed_events/rejection новых recovery events и unchanged Day 14 bounded contract, fail-closed cross-version State/setup без migration; зафиксировать passed checks без повторения старых A/B/live.
- [x] 7.3 Выполнить актуальные Android unit/build и затронутые Playground/navigation UI checks через PowerShell 7 scripts/dev.ps1; проверить результаты одной managed Gradle session без concurrent wrapper/IDE build, повторяя только проверки с изменившимися входами.
- [x] 7.4 Подготовить live отдельно от offline checks: проверить scripts/dev.ps1 status, managed backend stdout/stderr и доступность backend с эмулятора; readiness evidence не должно выдавать /health за подтверждение доступности provider.
- [x] 7.5 Пройти согласованный live flow design.md в одном разговоре: пять normal Sends (включая correction discussion), один forbidden skip на Plan Approval, Pause/Resume, explicit VALIDATION_FAILED обратно в Implementation, повторный forward через Validation до Done; зафиксировать фактические calls/commits/adherence и recovery Inspector, без automatic repair/retry или выдуманного test verdict. Второй forbidden skip и requirements recovery оставить обязательными offline checks.

- [x] 7.6 Добавить deterministic matrix обоих recovery edges: exact target/revision +1, прежние task/machine/status, equality всех non-State sources/revisions (conversation, Working/Long-term, Profile/binding, policy/config), zero provider calls, точные allowed_events recovered node, rejection из unrelated node/повторного event/PAUSED/DONE; после каждого recovery пройти forward до Validation/Done. Проверить stale CAS/write failure/unknown acknowledgement, reopen с checkout-v2 без replay и immutable recovery receipt после следующего forward event.

## 8. Documentation and completion evidence

- [x] 8.1 Создать day-15-agent-playground/README.md с русскими разделами «Суть эксперимента», «Что проверяет», «Результаты» и ссылками на component instructions; кратко отразить различие allowed forward/recovery и forbidden skip, проверить, что отсутствуют выдуманные успешные результаты и semantic guarantee шире bounded coverage.
- [x] 8.2 Добавить относительную ссылку Day 15 в раздел «Задания» корневого README в порядке дней без дублей; проверить существование целевого Day README и наличие ссылки в diff текущего change.
- [x] 8.3 Обновить только необходимые backend/Android/scripts README для нового API/setup/recovery и команд проверки; проверить, что Day README не дублирует длинные инструкции, технический сценарий остаётся в OpenSpec и секреты/локальные данные не попадают в изменения.
- [x] 8.4 Сверить итоговую реализацию и factual results со specs/tasks, проверить синтаксис изменённых файлов, git diff --check и openspec validate day-15-agent-playground --strict; отдельно перечислить непроведённый live/ручную проверку, если они остались, без автоматического commit/push/archive.
