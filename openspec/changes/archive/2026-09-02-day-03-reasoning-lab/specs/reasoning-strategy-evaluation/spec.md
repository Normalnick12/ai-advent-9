## Purpose

Задаёт воспроизводимый backend-контракт для сравнения четырёх prompting-стратегий на одной задаче с независимой детерминированной оценкой качества и полными метриками вызовов.

## ADDED Requirements

### Requirement: Fixed optimization benchmark
Система SHALL использовать во всех запусках Reasoning Lab одну неизменяемую задачу: лимит 15 story points; фичи A `(cost 4, value 8)`, B `(6, 11)`, C `(5, 10)`, D `(3, 6)`, E `(7, 13)`, F `(2, 4)`, G `(4, 7)`, H `(5, 8)`; B несовместима с E, C допустима только вместе с F, A несовместима с D, G несовместима с H, а суммарная стоимость не превышает 15.

#### Scenario: Every strategy receives the canonical task
- **WHEN** клиент запускает Reasoning Lab
- **THEN** каждый финальный solver-вызов получает одинаковый канонический текст задачи со всеми фичами и ограничениями

#### Scenario: Canonical optimum is reproducible
- **WHEN** backend перебирает все `2^8` подмножеств фич
- **THEN** уникальным оптимумом является набор A, C, F, G со стоимостью 15 и ценностью 29

### Requirement: Comparable reasoning strategies
Система SHALL выполнять ровно четыре стратегии `DIRECT`, `STEP_BY_STEP`, `META_PROMPT` и `EXPERT_PANEL`, фиксируя для всех API-вызовов модель `gpt-5.6`, `reasoning.effort=medium`, стандартный reasoning mode и `max_output_tokens=1200`. Финальные solver-вызовы SHALL отличаться только strategy-инструкцией и SHALL использовать одинаковые задачу и Structured Output contract.

#### Scenario: Direct strategy has no extra reasoning instruction
- **WHEN** выполняется `DIRECT`
- **THEN** модель получает каноническую задачу и контракт ответа без дополнительной инструкции о способе рассуждения

#### Scenario: Step-by-step strategy requests explicit decomposition
- **WHEN** выполняется `STEP_BY_STEP`
- **THEN** к тем же задаче и контракту добавляется только инструкция решить задачу пошагово и кратко отразить проверку в `explanation`

#### Scenario: Expert panel is role prompting only
- **WHEN** выполняется `EXPERT_PANEL`
- **THEN** один prompt просит смоделировать последовательный вклад аналитика, инженера и критика перед единым финальным ответом
- **AND** backend выполняет ровно один OpenAI API-вызов и не создаёт subagents, отдельные agent sessions или tool-based делегирование

### Requirement: Meta-prompt uses two calls
Стратегия `META_PROMPT` SHALL сначала получить улучшенный prompt от модели, затем передать его второму вызову для решения канонической задачи. Оба вызова SHALL использовать те же `gpt-5.6`, reasoning effort и token limit; preparatory-вызов SHALL возвращать строгий объект с `generated_prompt`, а финальный вызов SHALL использовать общий solution contract.

#### Scenario: Generated prompt is used and exposed
- **WHEN** первый META_PROMPT вызов успешно возвращает `generated_prompt`
- **THEN** второй вызов решает задачу с использованием этого prompt
- **AND** итог стратегии содержит точный сгенерированный prompt для просмотра клиентом

#### Scenario: Meta-prompt metrics cover the whole pipeline
- **WHEN** оба META_PROMPT вызова завершены
- **THEN** latency измеряется от начала первого до конца второго вызова
- **AND** token usage суммирует usage обоих ответов
- **AND** `api_call_count` равен 2

### Requirement: Common structured solution contract
Каждый успешный финальный solver-вызов SHALL возвращать strict Structured Output с обязательными полями `selected_features`, `total_cost`, `total_value` и `explanation`, без дополнительных свойств. `selected_features` SHALL содержать только идентификаторы A–H, а числовые итоги SHALL быть целыми числами.

#### Scenario: Structured result is returned to the client
- **WHEN** финальный OpenAI response имеет статус `completed` и проходит parsing
- **THEN** backend возвращает типизированное решение с выбранными фичами, стоимостью, ценностью и объяснением

#### Scenario: Invalid structured response is isolated
- **WHEN** финальный ответ incomplete, не разбирается или нарушает контракт
- **THEN** соответствующая стратегия возвращается как `incorrect` с описанием ошибки
- **AND** результаты остальных стратегий не теряются

### Requirement: Deterministic solver and verifier decide correctness
Backend SHALL вычислять оптимум полным перебором без LLM и SHALL проверять модель по фактически выбранному множеству, самостоятельно пересчитывая стоимость, ценность и ограничения. Стратегия SHALL считаться `correct` только если выбранное множество допустимо и оптимально, а заявленные `total_cost` и `total_value` совпадают с пересчитанными значениями.

#### Scenario: Optimal consistent answer is correct
- **WHEN** модель выбирает A, C, F, G и сообщает cost 15 и value 29
- **THEN** verifier помечает стратегию как `correct`

#### Scenario: Feasible but suboptimal answer is incorrect
- **WHEN** выбранное множество удовлетворяет ограничениям, но имеет value меньше 29
- **THEN** verifier помечает стратегию как `incorrect`
- **AND** сообщает, что решение не оптимально

#### Scenario: Reported totals cannot fool the verifier
- **WHEN** модель сообщает cost или value, не совпадающие с пересчётом выбранных фич
- **THEN** verifier помечает стратегию как `incorrect`, даже если заявленное value равно 29

#### Scenario: Constraint violation is incorrect
- **WHEN** выбранное множество содержит неизвестную или повторяющуюся фичу либо нарушает любое ограничение задачи
- **THEN** verifier помечает стратегию как `incorrect` и возвращает причины проверки

### Requirement: Strategy metrics and batch API contract
`POST /api/v1/reasoning-lab/run` SHALL запускать все четыре стратегии и возвращать по каждой: strategy id, русское display name, `correct`, latency в миллисекундах, token usage как минимум с input/output/total tokens, `api_call_count`, решение или ошибку и, только для META_PROMPT, generated prompt. DIRECT, STEP_BY_STEP и EXPERT_PANEL SHALL иметь `api_call_count=1`.

#### Scenario: Successful batch contains all strategies
- **WHEN** клиент отправляет корректный пустой запрос запуска
- **THEN** ответ содержит ровно по одному результату для всех четырёх стратегий с сопоставимыми метриками и общей конфигурацией эксперимента

#### Scenario: One upstream failure does not fail the batch
- **WHEN** OpenAI-вызов одной стратегии завершается timeout или upstream error
- **THEN** batch-ответ сохраняет результаты остальных стратегий
- **AND** сбойная стратегия имеет `correct=false`, фактический `api_call_count`, измеренную latency и безопасную error-информацию без prompt или секретов

#### Scenario: No API secret crosses the backend boundary
- **WHEN** Reasoning Lab вызывается Android-клиентом или возвращает ошибку
- **THEN** `OPENAI_API_KEY` читается только backend и никогда не включается в response, логи или generated prompt
