## Purpose

Определяет воспроизводимый backend-контракт для сравнения одного запроса при трёх значениях temperature с фиксированными остальными параметрами, формальной benchmark-проверкой и сопоставимыми метриками.

## ADDED Requirements

### Requirement: One batch varies only temperature
`POST /api/v1/temperature-lab/run` SHALL принимать один непустой `prompt` и возвращать результаты ровно для `temperature=0`, `temperature=0.7` и `temperature=1.2`. Во всех трёх OpenAI Responses API вызовах SHALL совпадать `model="gpt-5.6"`, точное значение `prompt`, `reasoning.effort="none"`, standard reasoning mode, `max_output_tokens=600`, output contract, storage/cache policy, tools и все остальные параметры; SHALL различаться только `temperature`. Параметр `top_p` SHALL не передаваться, чтобы сохранить его default-значение.

#### Scenario: Comparable three-result batch
- **WHEN** backend принимает допустимый prompt запуска Temperature Lab
- **THEN** он выполняет по одному вызову для temperature 0, 0.7 и 1.2
- **AND** batch response содержит три результата в стабильном порядке 0, 0.7, 1.2 и общую read-only конфигурацию эксперимента

#### Scenario: Request envelopes differ only by temperature
- **WHEN** сравниваются фактические параметры трёх вызовов одного batch
- **THEN** после исключения поля `temperature` их параметры полностью идентичны
- **AND** ни один вызов не содержит явно заданного `top_p`

### Requirement: Canonical prompt selects benchmark mode
Система SHALL считать запуск benchmark-режимом только при точном посимвольном совпадении request prompt со следующим каноническим текстом, включая порядок, пунктуацию и переносы строк:

```text
Придумай ровно 5 названий для мобильного приложения, которое помогает разработчикам готовиться к техническим собеседованиям.

Для каждого названия придумай короткий рекламный слоган.

Требования:

1. Название должно состоять из 1–2 слов.
2. Все 5 названий должны различаться.
3. В названиях нельзя использовать отдельные слова «Interview», «AI» и «ИИ».
4. Каждый слоган должен содержать не более 8 слов.
5. Названия и слоганы должны быть уместны для продукта подготовки разработчиков к техническим собеседованиям.

Не добавляй вступление, заключение или дополнительные комментарии.
```

#### Scenario: Exact canonical prompt uses benchmark mode
- **WHEN** request prompt точно совпадает с каноническим текстом
- **THEN** backend сообщает режим `benchmark` и применяет benchmark output contract и validator ко всем трём результатам

#### Scenario: Any edited prompt uses free mode
- **WHEN** request prompt отличается от канонического хотя бы одним символом, пробелом или переносом строки
- **THEN** backend сообщает режим `free`
- **AND** не нормализует и не заменяет пользовательский текст перед тремя OpenAI-вызовами

### Requirement: Benchmark uses one strict structural contract
В benchmark-режиме каждый temperature-вызов SHALL использовать один и тот же strict Structured Output: объект с единственным обязательным массивом `variants`, элементы которого являются объектами с обязательными строковыми полями `name` и `slogan`, без дополнительных свойств. JSON Schema SHALL фиксировать только структуру и SHALL NOT задавать `minItems`, `maxItems` или иным способом принуждать массив содержать ровно пять элементов.

#### Scenario: Model returns a structurally valid non-five count
- **WHEN** OpenAI возвращает структурно допустимый объект с количеством `variants`, отличным от пяти
- **THEN** parsing считается успешным и все полученные варианты доступны клиенту
- **AND** нарушение количества выявляет backend validator, а не JSON Schema

#### Scenario: Structured output is identical across temperatures
- **WHEN** backend строит три benchmark-вызова одного batch
- **THEN** имя, strict-флаг и полная JSON Schema output contract совпадают во всех трёх вызовах

### Requirement: Backend independently evaluates five formal criteria
Для каждого успешно разобранного benchmark-ответа backend SHALL без участия LLM вычислять пять отдельных Boolean-проверок и итоговое количество выполненных требований от 0 до 5: (1) возвращено ровно пять вариантов; (2) каждое `name` содержит 1–2 слова; (3) все `name` уникальны после trim, collapse внутренних whitespace и Unicode case-insensitive normalization; (4) ни одно `name` не содержит отдельного case-insensitive слова `Interview`, `AI` или `ИИ`; (5) каждый `slogan` содержит не более восьми слов. Для проверок длины слова SHALL считаться непустыми токенами, разделёнными whitespace; запрещённые слова SHALL распознаваться как отдельные Unicode letter/digit tokens, поэтому составные строки без границы слова не запрещаются.

#### Scenario: Fully compliant benchmark answer
- **WHEN** ответ содержит ровно пять вариантов, все названия состоят из 1–2 слов, нормализованно уникальны и не содержат запрещённых отдельных слов, а все слоганы имеют не более восьми слов
- **THEN** validator возвращает пять успешных проверок и `requirements_met=5`

#### Scenario: Normalized duplicates are rejected
- **WHEN** два названия различаются только регистром, ведущими/замыкающими пробелами или количеством внутренних whitespace
- **THEN** проверка уникальности не выполнена
- **AND** остальные четыре критерия оцениваются независимо по фактическому ответу

#### Scenario: Forbidden standalone word is rejected
- **WHEN** название содержит `Interview`, `AI` или `ИИ` как отдельный токен в любом регистре, включая соседство с пунктуацией
- **THEN** проверка запрещённых слов не выполнена
- **AND** совпадение внутри более длинного letter/digit token само по себе не считается отдельным запрещённым словом

#### Scenario: Compliance is not an accuracy or creativity score
- **WHEN** benchmark validation возвращается клиенту
- **THEN** контракт описывает её как «Соблюдение требований: N/5» и предоставляет результаты пяти формальных проверок
- **AND** backend не вычисляет accuracy, Creativity Score, семантическую уместность или иную численную оценку качества

### Requirement: Edited prompts use ordinary text responses
В free-режиме все три вызова SHALL получать точный пользовательский prompt и один обычный text output contract. Benchmark Structured Output, formal validator и извлечение или подсчёт названий SHALL быть отключены, а response SHALL явно сообщать, что автопроверка benchmark недоступна для произвольного запроса.

#### Scenario: Free-mode comparison completes
- **WHEN** пользователь запускает непустой изменённый prompt
- **THEN** каждый успешный temperature-результат содержит обычный текстовый ответ, temperature, token usage и отдельную latency
- **AND** поля benchmark validation и variants отсутствуют либо имеют `null`

#### Scenario: Free-mode prompt remains byte-for-byte equivalent as text
- **WHEN** backend формирует три free-mode OpenAI request
- **THEN** значение input string во всех трёх запросах точно равно строке из API request
- **AND** backend не дописывает benchmark instructions к пользовательскому тексту

### Requirement: Per-temperature results preserve metrics and partial failures
Batch response SHALL возвращать для каждой temperature отдельные status, monotonic `latency_ms`, token usage как минимум с input/output/reasoning/total tokens, ответ либо безопасную ошибку и benchmark validation только когда она действительно была выполнена. Ошибка, incomplete response или parse failure одной temperature SHALL NOT удалять результаты остальных temperature и SHALL NOT запускать скрытый повтор с изменённой конфигурацией.

#### Scenario: One temperature fails upstream
- **WHEN** один OpenAI-вызов завершается timeout, incompatible-parameter error, incomplete response или parse failure
- **THEN** соответствующий результат содержит фактические status, latency, доступный usage и безопасную error-информацию
- **AND** два остальных результата остаются в batch response
- **AND** невыполненная formal validation отображается как недоступная, а не как выдуманное `0/5`

#### Scenario: Latency remains an observation
- **WHEN** batch возвращает три latency
- **THEN** каждая latency измеряет только соответствующий OpenAI-вызов
- **AND** backend не объявляет разницу latency причинным эффектом temperature

#### Scenario: No secret crosses the backend boundary
- **WHEN** Temperature Lab завершается успехом или ошибкой
- **THEN** `OPENAI_API_KEY` читается только backend и не включается в response, prompt, логи или диагностические поля клиента
