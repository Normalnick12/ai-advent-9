## ADDED Requirements

### Requirement: Day 14 presentation explains mandatory rules and bounded guarantees

Каталог и экран SHALL показывать «День 14» и «Инварианты и ограничения состояния». UI SHALL различать Memory facts, Profile preferences, workflow State и обязательные invariants. Checks SHALL обозначать проверку typed proposal, без обещания проверки всего natural-language смысла, исходников или реальной оплаты. Prevention instructions SHALL не называться enforcement guarantee. Known semantic refusal SHALL отличаться от configuration/technical error; отсутствие проверки SHALL не отображаться pass. Основной экран SHALL использовать понятные русские labels, а canonical tokens/IDs/raw diagnostics SHALL сохраняться в inspector без искажения.

#### Scenario: User sees the actual guarantee
- **WHEN** proposal прошёл deterministic validation
- **THEN** UI сообщает о принятом предложении в рамках заданных правил, не утверждая, что произвольная реализация MVI проверена

#### Scenario: Failure does not look like a normal refusal
- **WHEN** обязательный validator технически не выполнился
- **THEN** показана ошибка проверки, а не утверждение о конфликте запроса с конкретным invariant

#### Scenario: Narrow screen keeps the compact lab usable
- **WHEN** экран узкий или увеличен системный шрифт
- **THEN** правила, actions, final response и inspector доступны прокруткой, длинные тексты переносятся и не перекрываются системными панелями
