## Why

Days 11–13 отделили факты, предпочтения и workflow, но ordinary Send сохраняет любой пригодный completed ответ до проверки domain constraints. Day 14 добавляет обязательную границу принятия результата: проверяемое нарушение не попадает в ответ и Short-term, а степень гарантии явно ограничена тем объектом и свойствами, которые действительно проверены.

## What Changes

- Добавить provider-independent invariant contracts и небольшой generate-before-commit coordinator, сохранив прежний run_turn для старых Days.
- Реализовать task-scoped durable versioned coding policy: MVI, Compose, Coroutines/Flow и обязательное подтверждение оплаты в предлагаемом дизайне. Predicates остаются typed code; FSM constraints остаются в FSM.
- Перед generation проверять согласованность источников и controlled structured intent. Request conflict даёт deterministic refusal с нулём provider calls и commit user/refusal.
- Получать typed proposal через candidate-generation/parser adapter, валидировать policy и строить ответ trusted renderer. Generated invariant violation исключает raw candidate и сохраняет user/safe-refusal; configuration и technical enforcement errors не создают semantic refusal или conversation commit.
- Передавать invariants модели для prevention отдельно от блокирующего enforcement. Core получает parsed, structurally valid candidate и не зависит от structured-output формата provider.
- Добавить isolated backend API, компактный Android lab, actual request/candidate/validation/commit evidence; проверить compatible, controlled conflict и fake candidate violation, storage/recovery и минимальный live flow.

## Capabilities

### New Capabilities

- `agent-invariants`: invariant metadata/results, typed policy boundary, deterministic acceptance lifecycle и независимость от provider.
- `invariants-experiment`: durable task coding policy, controlled intents/proposals, source composition, observations и acceptance Day 14.
- `invariants-android`: compact lab, readiness, response/refusal/error, inspector и recovery.

### Modified Capabilities

- `first-agent-conversation`: additive validated-turn lifecycle Day 14 поверх общих generation/session/atomic pair primitives без изменения Day 02–13.
- `learning-days-navigation`: отдельный Day 14 destination, сохранение UI state и отсутствие replay.
- `learning-days-presentation`: карточка Day 14 и ясное различение hard rules, preferences, проверок и пределов гарантии.

## Impact

При реализации затрагиваются backend invariant domain/policy/storage, candidate adapter, request preparation, coordinator/API/composition root, Android Repository/ViewModel/Compose/navigation и scoped tests. Добавляются `day-14-invariants/README.md`, ссылка в корневом README и соответствующие component docs. Переиспользуются Memory/Profile/State, SimpleAgent.generate, AgentSession.commit, ConversationStore и LlmClient; старые namespaces/data не мигрируются. Новая инфраструктура и обязательные зависимости не требуются.

Generic policy DSL, expression trees/operators, runtime policy parser, arbitrary NLU classifier, universal semantic validator, обязательный reviewer, retries, реальные coding/payment side effects, FSM/Profile refactoring, integrated Playground и distributed transactions не входят в scope. Ограничения переносимости Day 13 renderer/Profile фиксируются как observations. Текущий workflow создаёт только planning artifacts.
