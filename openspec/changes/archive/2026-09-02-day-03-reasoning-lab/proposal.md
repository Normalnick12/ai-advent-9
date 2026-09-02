## Why

Day 03 должен на одном фиксированном оптимизационном примере наглядно сравнить четыре prompting-стратегии, не смешивая качество ответа модели с оценкой другой LLM. Для воспроизводимой демонстрации нужны общий контракт ответа, детерминированная проверка оптимума и единый экран с сопоставимыми метриками.

## What Changes

- Расширить существующий FastAPI backend отдельным запуском Reasoning Lab для стратегий DIRECT, STEP_BY_STEP, META_PROMPT и EXPERT_PANEL на модели `gpt-5.6` с одинаковыми reasoning effort, исходной задачей, финальным Structured Output contract и token limit.
- Реализовать META_PROMPT как два последовательных Responses API вызова: генерация улучшенного prompt и решение задачи; учитывать суммарные latency, usage и API call count обоих вызовов.
- Добавить детерминированный полный перебор `2^8` комбинаций и verifier, который независимо пересчитывает ограничения, стоимость, ценность и оптимальность результата модели.
- Возвращать для каждой стратегии решение, `correct`/`incorrect`, latency, usage и количество API-вызовов; для META_PROMPT также возвращать сгенерированный prompt. EXPERT_PANEL остаётся одним role-prompted вызовом без subagents.
- Добавить в существующий Android app отдельный простой Material 3 экран Reasoning Lab с русскими пользовательскими строками, запуском всех стратегий и читаемыми карточками результатов и метрик.
- Сохранить существующий Day 02 экран и его API, добавить backend/Android тесты для нового контракта и создать `day-03-reasoning-strategies/README.md` как точку входа задания.

## Capabilities

### New Capabilities

- `reasoning-strategy-evaluation`: фиксированная оптимизационная задача, четыре prompting-стратегии, общий контракт решения, детерминированная верификация и агрегированные метрики backend.
- `reasoning-lab-android`: русскоязычный экран существующего Android-приложения для запуска и сравнения результатов Reasoning Lab.

### Modified Capabilities

Нет: каталог основных OpenSpec specs пока пуст, а поведение Day 01/02 должно сохраниться.

## Impact

- Backend: новые Pydantic transport-модели, endpoint, orchestration/service для стратегий, solver/verifier и unit/API tests; существующий `/api/v1/generate` остаётся совместимым.
- Android: новые DTO/repository method, отдельные Reasoning Lab ViewModel и Compose screen, простой выбор между существующим и новым экранами внутри текущего `app` module, а также unit tests.
- Документация: новый `day-03-reasoning-strategies/README.md` и ссылки/инструкции запуска без секретов.
- Внешние зависимости не требуются: используются существующие FastAPI, Pydantic, официальный OpenAI Python SDK, Retrofit, kotlinx.serialization, coroutines и Material 3.
