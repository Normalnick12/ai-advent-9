## ADDED Requirements

### Requirement: Day 14 validates results before shared atomic conversation commit

Day 14 SHALL переиспользовать общие generation, session guards, context snapshot validation и atomic pair persistence primitives через отдельный validated-turn path. Завершение provider generation SHALL NOT само по себе запускать commit в Day 14. Candidate preparation, invariant acceptance и trusted rendering SHALL завершаться до публикации final answer и записи пары. Known request conflict и generated invariant violation SHALL сохранять user/deterministic-safe-refusal при успешном commit; configuration/technical enforcement/provider failures SHALL сохранять прежнюю conversation согласно agent-invariants. Day 02–13 API contracts, exact payloads, configs, timeouts/retries, call counts и commit semantics SHALL оставаться прежними; новые invariant instructions SHALL присутствовать только в новом namespace. Conversation acceptance SHALL NOT автоматически менять FSM, Working, Long-term, Profile или policy.

#### Scenario: Old ordinary sends retain their behavior
- **WHEN** Day 14 подключён и выполнены existing Day 06–13 ordinary/probe operations
- **THEN** прежние payloads/call counts и completed/probe commit rules сохраняются, Day 12 preferences не становятся hard gates и Day 13 events остаются explicit

#### Scenario: Candidate is not committed through the old immediate path
- **WHEN** Day 14 получает completed generation с known invariant violation
- **THEN** raw output никогда не появляется в runtime/durable conversation, только safe refusal может быть committed вместе с user

#### Scenario: Namespace identities cannot bypass the acceptance gate
- **WHEN** Day 14 task/session ID передан старому API либо чужой ID использован в Day 14
- **THEN** чужая conversation не открывается, provider calls и fallback отсутствуют

#### Scenario: Session ownership is preserved during validation
- **WHEN** Day 14 generation/validation ещё выполняется и приходит competing session/source action
- **THEN** conflicting action отклоняется, исходный turn освобождает guards при любом terminal outcome и не commit-ит пару в другую session
