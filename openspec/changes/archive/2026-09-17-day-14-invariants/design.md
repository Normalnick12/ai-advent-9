## Context

Мотивация и scope — в [proposal.md](proposal.md); terminal contracts — в [agent-invariants](specs/agent-invariants/spec.md). Design необходим: change вводит новый acceptance lifecycle между generation и storage и затрагивает backend, persistence и Android.

Текущие extension points:

- `backend/app/agent.py`: `generate()` не принимает session и не commit-ит; `run_turn()` сразу сохраняет пригодный completed output. Его validation проверяет пригодность текста, не domain invariants.
- `agent_sessions.py` и `sqlite_conversation_store.py`: session guard, immutable history tuple, atomic pair write; runtime history обновляется после store return.
- `agent_request.py`: pure Memory/Profile/State preparation; `memory_selection.py` проверяет соответствие session/history snapshot.
- `task_state_lab_service.py`: coherent source resolution/revisions и application busy guard; `llm_capture.py` записывает actual provider-neutral arguments.
- `llm_client.py`: общий provider boundary, но `AgentConfig.text_format` — существующий provider-shaped dictionary. Domain invariants не должны наследовать эту зависимость.
- Старые namespaces сохраняют собственные контракты; в частности Profile violation Day 12 не блокирует ordinary commit, а PAUSED model adherence Day 13 отделено от FSM enforcement.

## Goals / Non-Goals

**Goals:**

- Переиспользуемый bounded coordinator, единственный commit path которого принимает trusted final text после обязательного gate.
- Разделение structural candidate preparation, semantic domain predicates и storage confirmation.
- Проверяемый typed coding proposal и честная гарантия только его решений.
- Reusable core не требует task_id, конкретного workflow или классифицированного natural-language intent; task scope разрешается lab service.
- Воспроизводимое evidence для request conflict, model violation и technical failure.

**Non-Goals:**

- Общий AgentRuntime, policy DSL/registry, generic constraint solver, arbitrary policy JSON, reviewer/retry loop.
- Генерация/компиляция реальных исходников, реальная оплата и authorization внешних actions.
- Free-form chat UI, editor policies, owner policy storage, runtime multi-scope precedence engine.
- Рефакторинг Day 13 FSM renderer или Profile для новых доменов, смешанные workflows в одном store, migration старых Days.
- Distributed transaction, durable operation journal, exactly-once HTTP delivery или полная semantic safety.

## Decisions

### 1. Small contracts and typed policies

Предлагаемые модули обозначают responsibilities; точное разбиение файлов можно уточнить при реализации без изменения contracts:

| Responsibility | Proposed home | Depends on |
| --- | --- | --- |
| RuleRef/InvariantViolation/ValidationResult и immutable source metadata | `invariants.py` | Standard types; no lab/provider |
| Generic validated-turn lifecycle | `validated_turn.py` | Shared session/conversation primitives, injected candidate generator/check/render functions |
| CodingPolicy/CodingProposal/ControlledIntent и predicates | `coding_invariants.py` | Invariant contracts; no SDK/API/UI |
| Provider candidate generation and strict parsing | `coding_candidate_adapter.py` | SimpleAgent.generate/LlmClient, CodingProposal |
| Durable task coding policy adapter | `coding_policy_store.py` | CodingPolicy and persistence |
| Scope resolution, setup, guards, API receipts | `invariants_lab_service.py`, models/API | Memory/Profile/State/policy adapters and coordinator |

`RuleRef` хранит ID, scope/source и доверенное описание; `InvariantViolation` — rule ref, stage, reason code и optional typed attempted/required values. Metadata не содержит executable expressions. `ValidationResult` различает passed, violated и unavailable/error, перечисляет реально проверенные rules. Все обязательные правила должны быть проверены, а не только отсутствовать в violations.

Coding policy содержит конкретные поля и обычные typed predicates. Generic field/operator/value и промежуточный язык rules отвергнуты: доказана вариативность policy между агентами, но потребность в runtime DSL отсутствует. Не вводим четыре strategy interfaces ради будущих validators: injected typed callables или один маленький policy contract достаточны.

Scope metadata не диктует storage. Сегодня durable — task coding policy. Agent-level trusted definitions можно передать тем же gate в коде; owner/global policy management не реализуется. FSM transitions по-прежнему enforced resolver/event path. Support agent сможет заменить candidate type, predicates и renderer, не меняя lifecycle; реализация такого агента не входит в change.

### 2. Typed proposal is the accepted object

Day 14 proposal — ограниченное предложение изменений для Checkout retry, не исходный код. Минимальные поля:

| Field | Structural domain | Day 14 policy |
| --- | --- | --- |
| architecture | MVI, MVVM | MVI |
| ui_toolkit | Compose, Views | Compose |
| async_model | CoroutinesFlow, RxJava | CoroutinesFlow |
| payment_confirmation_required | strict boolean | true |
| retry_mode | manual, bounded_backoff | оба допустимы для retry загрузки, не отправки платежа |

Для bounded_backoff фиксированный trusted template описывает ограниченное число повторов загрузки; модель выбирает вариант, а не свободный код/числовые expressions. Это даёт модели реальный выбор внутри допустимого пространства. Domain values schema не сужается до единственного expected ответа: MVVM/RxJava/false structurally valid и проверяются отдельными predicates. Выбор UI=Views отдельно покрывается fake test даже если conflict button не меняет toolkit.

Strict structural parsing запрещает missing/extra fields, duplicate JSON keys, неверные типы, неизвестные enum values и trailing prose. Свободных `explanation`, `code` или Markdown fields нет. Несовпадение metadata и unchecked prose поэтому не может попасть в accepted output. Malformed output — technical candidate preparation error, не известное invariant violation.

Trusted renderer строит весь assistant answer по accepted fields. Raw JSON остаётся diagnostics, в history сохраняется rendered text. Для lab применяется fixed Compact Engineer profile; текст renderer согласован с его кратким русским оформлением, но не требует нового универсального Profile renderer. Policy predicates не зависят от style preferences.

Альтернативы: metadata+prose оставляет semantic mismatch; artifact validator полезен для настоящих файлов, но расширяет experiment до coding toolchain. В этом change гарантия — допустимость proposal fields и соответствующего шаблонного ответа. Проверка MVI исходников и факта payment approval не заявляется.

### 3. Provider-specific candidate adapter

```text
prepared messages/config
         |
candidate-generation adapter
         |
SimpleAgent.generate --> LlmClient --> provider
         |
strict parser
         |
typed candidate --> invariant predicates --> trusted renderer
```

Текущий adapter может использовать OpenAI structured output через существующий `text_format`, но schema/payload construction остаются adapter detail. В invariant predicates не передаются raw JSON, `LlmResult` или SDK models. Adapter возвращает typed candidate либо явный generation/preparation failure с отдельными diagnostic/usage data.

Другой provider может использовать иной generation/parser adapter. Он обязан возвращать тот же domain candidate и те же категории failures. Invariant policy/validation/results, gate и deterministic refusal rendering остаются прежними. Provider schema compliance не заменяет локальный strict parse и policy checks.

Один вызов adapter — максимум одна generation; нет count, repair, retry, extraction или reviewer call. Сохраняем существующие provider deadlines и без автоматического повторения. Конкретная fixed конфигурация Day 14 может переиспользовать текущую модель Day 13 с отдельной version; model choice не участвует в policy semantics.

### 4. Durable policy and explicit preparation

Task policy record: `task_id`, `policy_id`, `definition_version`, typed CodingPolicy values. Policy immutable после installation; fingerprint вычисляется из canonical record для references/receipts, не используется как security token. Редактирование и active-policy binding не нужны: current task однозначно выбирает один record. `create/read` contract не зависит от физического размещения.

SQLite adapter в `backend/.local/invariants/day14-v1/` допустим рядом с отдельными memory/profile/state stores. Четыре файла — только isolation layout, не требование reusable core. Adapter проверяет schema, typed records и version; read никогда не создаёт defaults. Same-record explicit create идемпотентен, replacement запрещён. Missing/corrupt/unsupported различаются.

Setup lab использует известные Day 13 Working values (Checkout loading/error/success, MVI, RC-42), Compact Engineer и checkout-v1. Явные действия создают missing sources; existing непустые несовпадающие values не перезаписываются. Workflow стартует initial и проходит REQUIREMENTS_READY/PLAN_APPROVED только через отдельные explicit confirmations. Готовность proposal operation требует ACTIVE execution. Это не меняет обычный Day 13 Send при PAUSED.

New Conversation сохраняет policy. New Task создаёт новые task/session и initial State, оставляя собственную policy preparation явной; previous sources остаются inactive. Profile/Long-term mutations не меняют policy. UI не обязан копировать полный редактор Memory/Profile прошлых дней. Все lab writes проходят один service guard. При partial setup current показывает реальные saved IDs и missing component; completion адресует их, а не повторяет New Task.

### 5. Coherent selection and pure request assembly

Под application guard service проверяет current identities, Memory snapshot, Profile/binding revisions, State revision и exact policy reference. Policy-aware consistency check сравнивает Working.current_architecture с required architecture. Missing обязательные fixture sources — readiness error; противоречивые — configuration error. Long-term preferred_architecture остаётся soft preference; существующий Working override сохраняется. Согласованность произвольного natural-language task text не заявляется.

Расширение `prepare_agent_request` — optional pre-rendered trusted invariant section, полученная только из backend typed policy. Когда секция отсутствует, output/messages/config должны совпадать с Day 13 побайтово. Preparation не читает stores и не выбирает policy. Instructions: base + PROFILE + TASK_STATE + ACTIVE_INVARIANTS; Memory остаётся data messages, затем active history и query. Candidate-format guidance добавляет adapter без примеси expected test results.

Precheck controlled intent может завершиться до assembly. Тогда receipt имеет null actual request/candidate и not-applicable assembly. CapturingClient стоит на actual LlmClient boundary после adapter-specific config preparation, поэтому receipt фиксирует фактический config, а не только общий preview. Сравнение с независимым recording delegate проверяет это различие.

### 6. Bounded coordinator owns the only commit path

Day 14 service владеет source resolution и policy choice; reusable coordinator принимает session, prepared context/проверяемый history snapshot, optional precheck result и typed generation/validation/rendering functions. Он не импортирует lab DTO, Checkout или Android enums. Не превращаем существующий `SimpleAgent.run_turn()` в универсальный runtime.

Coordinator устанавливает session guard, проверяет совпадение captured context и session history через существующую policy preparation, не добавляет pending user в durable history и освобождает guard в `finally`. Application guard удерживается логически на время await, SQL transaction — нет. Ошибки readiness/consistency до coordinator всё равно попадают в общий operation error envelope без provider call.

```text
resolve sources + consistency + history check
                    |
             intent precheck
                    |
       +------------+----------------+
       |                             |
  known conflict                 no conflict
       |                             |
 render safe refusal           generate + parse
       |                             |
       |                       typed validation
       |                             |
       |                  +----------+----------+
       |                  |                     |
       |                passed              violation
       |                  |                     |
       |           render final answer   render safe refusal
       |                  |                     |
       +------------------+---------------------+
                          |
                  atomic pair commit
                          |
                   confirmed result

Any configuration/technical failure --> operation error, no pair
```

Terminal table (commit column предполагает успешную запись):

| Outcome | Generation | Semantic final reply | Pair |
| --- | --- | --- | --- |
| accepted candidate | 1 | trusted rendered answer | user + answer |
| request conflict | 0 | deterministic refusal | user + refusal |
| generated invariant violation | 1 | deterministic safe refusal | user + refusal |
| configuration/consistency error | 0 | none | none |
| technical parser/validator/renderer failure | 0 or 1 by stage | none | none |
| provider refused/incomplete/error | 1 attempted | none | none |
| cancellation before commit | 0 or 1 attempted | none | none |

Ожидаемые violations возвращаются values, technical failures — отдельным error channel; исключение checker не преобразуется в `InvariantViolation`. Refusal для candidate failure объясняет отклонённый вариант, не обвиняя пользователя. Refusal renderer использует trusted descriptions и enum mappings, не raw text. Если не удалось сформировать безопасный отказ, turn заканчивается technical error без pair. Automatic regenerate отсутствует.

### 7. Honest storage and recovery boundary

В coordinator ровно один `AgentSession.commit(user, final_assistant)` после проверки и rendering. Используем существующий atomic pair store. Решение `accepted/refused` и статус commit хранятся раздельно; готовый текст не публикуется в main как completed success до подтверждения записи. При storage error decision остаётся diagnostics, operation — error, commit — failed либо unknown.

На write failure Day 14 service помечает свою session cache требующей reconciliation. После освобождения turn guard перечитывает durable session и переоткрывает собственный session manager/cache, не мутируя чужие Days и не пытаясь повторить append. Если чтение не удалось, recovery_required блокирует новые proposals до успешного read. Для подтверждённого rollback history прежняя; при неизвестном результате authoritative read показывает фактическую pair. Не требуется durable operation journal или replay. Commit без await не разрывается обычной task cancellation; если HTTP потерян после commit, пара остаётся durable и клиент только читает состояние.

Short-term и memory snapshot меняются после любой committed pair, включая refusal. Working/Long-term/Profile/State/policy остаются прежними. Не обещаем rollback остальных stores: во время proposal operation они вообще не записываются. Текущий guard корректен для одного backend worker и одного namespace writer; multi-worker deployment не включается.

### 8. Lab API and observations

Рекомендуемый prefix `/api/v1/invariants`. Минимальные operations: read scenario/current, explicit setup/missing-component preparation, existing-rule State confirmations, new-conversation/new-task и proposal с `action_id` + captured source references. Endpoint names можно согласовать с существующим API style при реализации; externally visible semantics определены specs. Произвольные policy JSON, raw instructions, provider config и history клиент не отправляет.

Backend catalog связывает `compatible-retry` и `conflicting-stack` с canonical user text и typed intent. Conflict меняет architecture, async и payment-confirmation, оставляя toolkit прежним. Display и сохранённый user text берутся из одной fixture. Reusable coordinator не требует intent: без него precheck отмечается unclassified/not-applicable, обязательный post-generation gate остаётся. Free-text lab action сегодня отсутствует.

Receipt разделяет `provider_dispatch`, `generation_calls`, `provider_outcome`, `candidate_preparation`, `assessment`, `decision`, `commit_status` и `operation_error`. HTTP success не означает dispatch. Error envelope сохраняет доступный receipt для technical failure; failure до разрешения sources не обязан содержать недоступные snapshots. `committed` не выводится из completed provider status. Raw rejected candidate доступен только diagnostic Inspector, не становится model context или final reply.

Runtime observations можно потерять при restart; reads не фабрикуют их из fixtures. Cumulative call count process-local, receipt count per-attempt. Для неизвестного network outcome dispatch/commit остаются unknown до доступных подтверждений, а runtime receipt не восстанавливается из одной только history.

### 9. Compact Android lab and documentation

Переиспользуются Repository/ViewModel/Compose patterns, AppContainer composition и existing day navigation. Main показывает четыре rules, краткие source summaries, две actions и final response/refusal/error. Setup — компактные явные действия вместо большого stepper; Inspector — техническое evidence. New Conversation/New Task доступны отдельно с ясным lifecycle.

Day 13 `publish()` безусловно выставляет dispatched после успешного API response: этот фрагмент не копируем. Day 14 использует backend dispatch/decision/commit fields. ViewModel recovery делает reads без повторных proposals/setup/events; Activity recreation и navigation сохраняют один in-flight job. UI не дублирует predicates или transition table.

Day README — кратко «Суть эксперимента», «Что проверяет», «Результаты» с честным статусом live. Detailed semantics/testing/setup остаются в OpenSpec/component docs. При реализации добавить относительную ссылку в корневой README. Work checklist для применения invariants: определить scope/источник истины, объект проверки, формализуемость, enforcement point, coverage, failure policy и соотношение стоимости/риска.

### 10. Verification and deferred extensions

Targeted UI checks: Back, rotation/in-flight, catalog round trip, historical receipt, narrow screen и isolation old Days. Existing accessibility tests сохраняются; mandatory dedicated increased-font/font-scale check не добавляется. Expanded font-scale проверяется только при реальном layout regression или отдельной accessibility задаче. Это ограничение объёма новых проверок не отменяет существующие требования доступности UI.

`scripts/dev.ps1` остаётся preferred path для Android checks, managed backend и readiness/status. Если pwsh/ExecutionPolicy недоступны, разрешён существующий fallback: прямые `gradlew.bat testDebugUnitTest`, `gradlew.bat assembleDebug` и scoped `gradlew.bat connectedDebugAndroidTest` из `android-app` с установленным JDK; backend из существующего Python-окружения в `backend` запускается командой `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` в управляемой терминальной сессии с stdout/stderr. Readiness/status проверяется прямым HTTP `/health` и read-only current, отдельно проверяется доступ с emulator; `/health` подтверждает backend, не OpenAI. Прямые Gradle commands не запускаются параллельно с Gradle/Android Studio в том же checkout. Исправление локального PowerShell tooling не входит в Day 14 и не является prerequisite проверок.

Проверки делятся на policy/persistence units, coordinator/fake integration, HTTP boundaries и Android Repository/ViewModel/UI. Fault injection отдельно покрывает malformed parsing, unavailable/throwing validator, failed renderer, atomic write rollback и unknown-outcome reconciliation. Technical paths не должны порождать refusal pair. Independent recording client подтверждает actual config, отсутствие отвергнутого candidate после reopen/в следующем input и call counts.

Reusable mechanism проверяется простым non-coding typed test candidate/predicate без реализации нового агента или workflow. Проверка двух candidate adapters на одинаковом typed result доказывает provider boundary. Structural/import checks исключают OpenAI/Android/Checkout зависимости из invariant contracts/coordinator. Regression scope охватывает затронутые общие primitives и exact payload tests старых Days; отдельный полный UI прогон оправдан только связанной навигацией.

Live — compatible + conflict, максимум одна generation на успешный двухоперационный flow. Нарушение live model фиксируется как факт; fake violation проверяется offline. Reviewer остаётся optional probabilistic extension, который может вернуть assessment на той же границе, но не становится deterministic guarantee. Artifact validators применяются в будущем к реальным файлам; human approval — к high-risk действиям с недостаточной автоматизируемостью. Для дешёвых formal rules используем deterministic checks; стоимость compiler/reviewer должна соответствовать проверяемому риску.

Known genericity observations Day 13: renderer содержит planning/implementation wording; Profile renderer содержит Android/Kotlin wording; SQLite State adapter получает одну definition на экземпляр и не является mixed-workflow registry. Эти ограничения фиксируются здесь, не исправляются в Day 14. `resolve` определяет допустимость transitions, CAS store — snapshot/revision; новые writes State должны идти через существующий event path. Для текущего Checkout fixture изменений FSM/Profile не требуется.

## Risks / Trade-offs

- [Checked metadata mistaken for correct architecture] -> Называть объект typed proposal, исключить unchecked prose, не заявлять code/semantic validation.
- [Technical error mistaken for invariant violation] -> Разные result/error channels и fault matrix с no-commit assertions.
- [Refusal introduces untrusted content] -> Только trusted templates и typed display values; renderer failure закрывает turn без pair.
- [Bypass through raw run_turn or stale session] -> Один coordinator commit path, session/history checks и namespace isolation regression.
- [Snapshot changes while awaiting provider] -> Single-worker application guard для всех Day 14 mutations; не держать SQL transaction через await.
- [Storage succeeded but response is lost] -> Read reconciliation, refresh affected session cache, no automatic replay; без exactly-once claims.
- [Bounded proposal provides less expressive answers] -> Это намеренная цена полностью проверяемого lab; свободный prose потребует другой явно ограниченной стратегии.
- [Policy abstraction grows into framework] -> Typed predicates, no runtime expressions, только реальные inputs текущего turn.
- [Current provider lacks useful candidate] -> Strict parser/gate сохраняют acceptance semantics; ошибка не скрывается retry, live result записывается фактически.

## Migration Plan

Реализация добавляет отдельный namespace, API и destination; старые databases не импортируются и не изменяются. Optional request-preparation extension сохраняет старые exact payloads. При первом открытии только reads; sources создаются explicit setup. Partial setup дополняется адресно без reset. Unsupported policy version не переинтерпретируется автоматически.

Rollback приложения отключает новый destination/API и оставляет Day 14 local data для последующего совместимого запуска; очищать данные, менять старые namespaces или переписывать их историю не требуется. Schema/version migration будущей policy является отдельным change. Реализация начинается только отдельным apply запросом после review этих artifacts.
