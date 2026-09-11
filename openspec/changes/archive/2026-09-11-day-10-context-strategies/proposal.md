## Why

Day 08 показывает рост полной истории, Day 09 — rolling summary с raw tail. Day 10 сравнивает другие представления conversation state на одном сценарии: локальное окно, устойчивые structured facts и независимые альтернативы. Цель — показать соответствие стратегии структуре задачи, не назначая победителя заранее; summary/compression в Day 10 отсутствуют.

Live v1 выявил failure Facts extractor: пропуск Turn 2 и три одинаковых ошибочных patches Turn 4. Validator сработал корректно. V2 усилил instructions, но live остановился на 7/8: extractor правильно извлёк B assertions, ошибочно выбрав replace для новых identities. V3 исправляет границу ответственности: LLM извлекает semantic facts, backend детерминированно выбирает state transition. V1/v2 остаются failed live evidence без исправления задним числом. Подробности и границы доказательств — в [design](design.md#v1-live-evidence-and-v2-scope).

## What Changes

- Добавить три независимых immutable runs `window | facts | branches` в isolated config-versioned Day 10 SQLite store, сохранив один `SimpleAgent` и прежние Day 02–09 semantics.
- Sliding передаёт последние шесть confirmed messages плюс current user; durable audit history не является доступным модели fallback.
- Facts v3 извлекает typed scoped semantic changes `set | cleared` через fixed `gpt-4o-mini` Structured Output только из exact current user. Backend после strict validation применяет deterministic add/update/no-op/clear к фактическому previous FactState; LLM не выбирает add/replace. Candidate facts и новая пара сохраняются одной транзакцией только после completed response.
- Branching хранит один shared prefix, один checkpoint после шестого scenario turn и ровно две независимые ветки A/B без копирования prefix, merge или nested branches.
- Зафиксировать восемь настоящих committed scenario Sends «Бронирование переговорных», одинаковые raw fixtures и две explicit side-effect-free final evaluations A/B из immutable final snapshots. Evaluation questions/replies не становятся conversation messages, не обновляют facts и не влияют друг на друга.
- Сравнивать deterministic качество двух ТЗ N/11, retention перед generation N/11, branch isolation, actual response/maintenance tokens с unknown coverage и объективные strategy-management actions.
- Добавить scenario-first Android экран с независимым progress, compact fixture cards и raw disclosure, facts inspector, checkpoint/A/B selector и read-only comparison dashboard.
- Сохранять evaluation outputs отдельно от conversations для restore, не вводя persistent billing journal. Live acceptance и видео фиксируют actual результаты отдельно от offline tests.

- Перейти на immutable `day10-gpt4o-mini-n6-v3` и extraction schema `facts-v2` без поля op. Сохранить strict assertion/evidence/type/value/duplicate validation и whole-patch atomicity; неизвестный clear отклонять. Это новый semantic contract, не recovery ошибочного v2 replace.
- Сохранить v1/v2 databases/runs без migration/delete/import/fallback; финальный comparison строить только по чистым Window/Facts/Branching v3 runs после отдельного manual live этапа. Scenario/model/N/Sliding/Branching/evaluation/metrics и raw fixtures не менять.

## Capabilities

### New Capabilities

- `context-strategies-experiment`: backend runs/storage, Sliding/Facts/Branching, точные fixtures, non-committing evaluation, deterministic metrics и accounting.
- `context-strategies-android`: scenario-first UI, независимые run states, restore/reconciliation, strategy visualizations и dashboard.

### Modified Capabilities

- `first-agent-conversation`: добавить гарантии общего Agent subsystem и совместимости Day 10 с прежними namespaces, без изменения исторических payloads/calls.
- `learning-days-navigation`: добавить Day 10 в каталог и независимые переходы main/dashboard/inspectors без provider calls.
- `learning-days-presentation`: добавить русскую identity Day 10 и точные подписи метрик, не изменяющие experiment data.

## Impact

Backend: узкий Day 10 preparation/commit path рядом с существующим Agent lifecycle, новый scoped store/topology/extractor/evaluation API, optional Structured Output в общем payload builder, reuse `TokenCounter`/`TokenUsage`. Старые database files не мигрируются; зависимости остаются FastAPI/Pydantic/официальный OpenAI SDK/SQLite.

Android: один screen-level MVVM state с тремя независимыми runs, Repository/DTO, небольшие локальные Compose components; wiring в AppContainer/MainActivity/AppRoot/catalog. Не нужны новый navigation framework, Agent implementations, generic strategy/plugin/dashboard frameworks.

Проверки: deterministic backend/JVM/UI suites, exact-payload/call-count regression Day 02–09, отдельный live acceptance. При реализации добавить краткий `day-10-context-strategies/README.md`; настройка и команды остаются в component README. Первоначальные apply v1/v2 выполнены; их deterministic отчёт находится в [validation](validation.md). Последующее failed live evidence v1/v2 и v3 contract описаны в [design](design.md). V3 delta реализован и проверен deterministic backend/JVM tests; отчёт — в [validation](validation.md#v3-implementation-and-deterministic-verification). Controlled live v3, видео и restart/restore/reset подтверждены пользователем; Section 12 завершён. Exact observations, incomplete token coverage и границы одного прогона — в [финальном отчёте](validation.md#final-v3-controlled-live-acceptance-user-confirmed).
