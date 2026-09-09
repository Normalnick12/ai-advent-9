# Day 08 — ранняя проверка внешнего контракта

## Статус apply

Проверка выполнена 2026-09-09 по явному разрешению пользователя на tasks 1.1–1.2. Обнаружен blocker baseline B. Реализация остановлена до изменения application code. Task 1.1 завершена проверкой SDK и записью конфигурации/цен ниже; task 1.2 остаётся открытой, поскольку integer B/H/F и oversized F не получены.

## Config / pricing record — task 1.1

- Configuration version: `day08-gpt4o-mini-v1`.
- Requested model: `gpt-4o-mini`; документированный snapshot для pricing allowlist: `gpt-4o-mini-2024-07-18`.
- Instructions: существующее значение `AgentConfig().instructions` из `backend/app/llm_client.py`, без изменений.
- Context window: 128000; model max output: 16384; laboratory reserved output: 1200.
- Generation configuration по design: `service_tier="default"`, `truncation="disabled"`, `store=false`, plain text; reasoning object отсутствует, retries=0. Generation в этой проверке не вызывалась.
- Зафиксированные Standard rates на 2026-09-09, USD / 1M tokens: uncached input **0.15**, cached input **0.075**, output **0.60**. У GPT-4o Mini нет отдельной cache-write надбавки: known writes оплачиваются по обычной input rate. Reasoning не тарифицируется повторно поверх output.
- Источники: [model / limits / alias / rates](https://developers.openai.com/api/docs/models/gpt-4o-mini), [cache-write semantics](https://developers.openai.com/api/docs/guides/prompt-caching), [counting guide](https://developers.openai.com/api/docs/guides/token-counting), [Python count reference](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens).
- Установленный `openai` SDK: **2.54.0**. Проверена локальная signature `AsyncInputTokens.count`: принимает model, instructions, input, text, truncation; generation-only max_output_tokens, service_tier и store в count не передавались. tiktoken не добавлен. Day 05 не изменён.

Это запись проверенной документации и локального SDK, а не подтверждение account/model access или actual generation pricing.

## Фактический provider-count smoke — task 1.2

Начало: **2026-09-09T17:01:06.803552+00:00**. Использован официальный `https://api.openai.com/v1`, `AsyncOpenAI`, timeout 15 секунд (connect 5), `max_retries=0`. Ключ прочитан из backend environment без вывода значения.

Выполнен один `POST /v1/responses/input_tokens` для B с такими аргументами:

```python
model="gpt-4o-mini"
instructions=AgentConfig().instructions
input=[]
text={"format": {"type": "text"}}
truncation="disabled"
```

Provider вернул:

```json
{
  "http_status": 400,
  "error_code": "missing_required_parameter",
  "error_type": "invalid_request_error",
  "error_param": null,
  "error_message": "One of \"input\" or \"previous_response_id\" or 'prompt' or 'conversation' must be provided."
}
```

Это отказ count endpoint принять согласованный пустой baseline input, **не context overflow** и не доказательство недоступности модели. B unavailable; H/F не вычислялись. Поддержка oversized counting остаётся непроверенной. Никакие absent counters не заменены нулём или estimate.

Итого: **1 count request, 0 generation requests, 0 history commits**. Не создавались application sessions и SQLite-файлы; существующая history не открывалась и не изменялась. После отказа B другие варианты input не пробовались, oversized request не отправлялся.

## Требуется review

Нужно согласовать дальнейшее исследование или изменение baseline-контракта: утверждённый B с `input=[]` фактически отвергнут provider. Пустой dummy message, другой tokenizer, другая модель и другие fallback здесь не вводились. До review apply остановлен; short/long live и настоящий overflow acceptance остаются открытыми. Backend/JVM/UI/build не запускались, поскольку реализация не начата.

## Повторный smoke нового контракта — 2026-09-09

Этот раздел фиксирует отдельный запуск после review независимых current/history/full measurements. Все предыдущие разделы выше сохранены как история первого baseline failure и остановки на тот момент; прежний HTTP 400 не переписан как success. Основная реализация по прямому указанию пользователя не продолжалась.

Начало нового запуска: **2026-09-09T17:18:23.633234+00:00**. SDK **2.54.0**, model **gpt-4o-mini**, официальный endpoint `POST https://api.openai.com/v1/responses/input_tokens`, timeout 15 секунд (connect 5), `max_retries=0`. Дополнительный transport guard разрешал только POST на этот host/path и считал фактические отправки. Generation endpoint не вызывался. Ключ читался из backend environment без вывода значения.

Первый current-only count имел payload:

```json
{
  "model": "gpt-4o-mini",
  "input": [
    {"role": "user", "content": "Какой мой кодовый цвет? Ответь кратко."}
  ],
  "text": {"format": {"type": "text"}},
  "truncation": "disabled"
}
```

Instructions, saved history, reasoning и generation-only параметры в этом запросе отсутствовали.

Фактический результат:

```json
{
  "result": "blocked",
  "stage": "current_only",
  "exception_type": "APITimeoutError",
  "count_calls": 1,
  "generation_calls": 0
}
```

HTTP status, structured provider error body и input_tokens не получены. Это transport timeout, а не доказательство неподдерживаемого payload, недоступности модели или context overflow. Количество токенов unavailable; ноль/estimate не подставлялись. После первого failure выполнена обязательная остановка без retry.

| Обязательный контракт | Результат | Provider count |
|---|---|---|
| Current-only | APITimeoutError | unavailable |
| History-only | Не запускался после первого failure | unavailable |
| Full request | Не запускался после первого failure | unavailable |
| Oversized full | Не запускался после первого failure | unavailable |

Подготовленная, но не отправленная synthetic history fixture: user «Мой кодовый цвет — янтарный. Ответь кратко.», затем assistant «Ваш кодовый цвет — янтарный.». Это явно тестовые тексты, не фактически сгенерированный диалог. Full использовал бы эту history, тот же current и существующие `AgentConfig().instructions`; SHA-256 UTF-8 instructions: `692ffef60e824f8cb67594abc411f7c563072e199645fb3a8a2464ce2d7147e9`. До full и deterministic oversized recipe выполнение не дошло.

Итого нового запуска: **1 count request, 0 generation requests, 0 history commits**. Совместно с первым историческим запуском: 2 count requests, 0 generation. Application sessions не создавались; SQLite и implementation code не изменялись. Actual generation usage и monetary cost не получены. Overflow execute не выполнялся, настоящий overflow acceptance не подтверждён.

Task 1.2 остаётся открытой. Новый count contract gate пока не пройден; apply остановлен без изменения architecture и без fallback. Для следующей попытки требуется новое указание пользователя; автоматического повтора нет.

## Разрешённый повтор с timeout 60 секунд — 2026-09-09

### Диагностика предыдущего timeout

В запуске 17:18 UTC был задан `httpx.Timeout(15, connect=5)` одновременно на HTTPX transport и AsyncOpenAI: connect=5, read/write/pool=15 секунд; `max_retries=0`. Tool зафиксировал **6.8200231 секунды для всего процесса**, включая запуск Python/импорты/создание клиента. Это не elapsed отдельного API request. В ветке исключения прошлого скрипта elapsed и тип вложенной transport cause не выводились, поэтому точное время и фазу прошлого APITimeoutError восстановить нельзя. Connect limit 5 секунд мог объяснять ранний timeout, но это только гипотеза, не установленная причина.

Проверен установленный OpenAI SDK: transport timeout оборачивается в `APITimeoutError` с сохранением исходного исключения через cause; при `max_retries=0` retry branch не выполняется. Сам по себе timeout без HTTP response не доказывает неподдерживаемость contract, недоступность модели или context overflow.

### Конфигурация и транспорт нового запуска

Начало: **2026-09-09T17:27:16.545461+00:00**. OpenAI SDK **2.54.0**, HTTPX **0.28.1**. Выполнен ровно один разрешённый повтор current-only; остальные стадии последовательно выполнялись только после успеха предыдущей.

- Fixed model: `gpt-4o-mini`; endpoint: `POST https://api.openai.com/v1/responses/input_tokens`.
- `httpx.Timeout(60.0)` на transport/client и явный timeout аргумент каждого count. Request hook подтвердил **connect/read/write/pool = 60.0 секунд** для каждого запроса. Это HTTPX phase timeouts; elapsed измерен отдельно монотонными часами вокруг SDK count/чтения ответа.
- SDK `max_retries=0`; application automatic retries=0. Коррекция размера oversized candidate является следующим утверждённым count probe, не повтором упавшего запроса.
- Transport guard разрешал только POST на официальный input_tokens host/path. Generation endpoint запрещён этим guard и не вызывался.
- Переменные HTTP_PROXY, HTTPS_PROXY, ALL_PROXY, NO_PROXY отсутствовали. Это проверка environment, не утверждение об отсутствии внешних сетевых посредников.
- Для current-only trace показал завершение TCP на 0.583 s от начала вызова, TLS на 1.101 s, response headers на 2.961 s. Ошибок транспорта в новом запуске не было.
- Timeout 60 секунд применён только к этой разрешённой smoke-проверке; application design/config не изменены.

### Фактические ответы

Все input_tokens прочитаны из provider JSON и проверены как non-negative integer, исключая bool. Первые три payload используют те же fixture texts/roles/order, которые зафиксированы в предыдущем разделе. Current/history не содержат instructions; full содержит существующие fixed Agent instructions, обе history messages и current. Совместимые settings: plain text и truncation disabled; reasoning, max_output_tokens, store, service_tier не отправлялись count endpoint.

| Count call | Контракт / candidate | HTTP | input_tokens | Elapsed, s |
|---|---|---|---:|---:|
| 1 | Current-only, одно user message | 200 | 19 | 2.965 |
| 2 | History-only, user + assistant | 200 | 35 | 0.415 |
| 3 | Full instructions + history + current | 200 | 139 | 0.375 |
| 4 | Oversized full, N=8192 | 200 | 82072 | 0.779 |
| 5 | Oversized full, N=13975 | 200 | 139902 | 0.495 |

Current/history/full являются самостоятельными structured measurements, не additive contributions. Их суммы/разности не использовались для вычисления системной части или oversized targeting. Это provider preflight, не actual generation usage.

### Oversized recipe и exact count

Использована та же synthetic saved history user/assistant, fixed instructions и ровно один новый oversized user message:

- Заголовок: «Это тест заполнения контекста. Далее следует повторяемый учебный ASCII-блок.» + LF.
- Повторяемый блок: `0123456789 abcdefghijklmnopqrstuvwxyz` + LF.
- Окончание: «Ответь кратко: принято».
- Первый N=8192. Следующий размер: `ceil(8192 * 140000 / 82072) = 13975` по design. Результат второго полного count измерен provider заново, а не оценён этой формулой.

Accepted exact full count **139902** находится в диапазоне **132000–160000** при model context window **128000**. Достаточно двух из максимум четырёх разрешённых candidate probes; общий oversized этап уложился в 90 секунд.

| Candidate | Current chars | Current UTF-8 bytes | Canonical full generation-shaped JSON bytes |
|---|---:|---:|---:|
| N=8192 | 311395 | 311474 | 320593 |
| N=13975 | 531149 | 531228 | 546130 |

Оба полных JSON меньше application resource cap 2 MiB. Generation-shaped JSON вычислялся только локально для размера/digest: count-compatible payload плюс max_output_tokens=1200, service_tier=default, store=false; он не отправлялся generation endpoint. Canonical serialization: sorted keys, UTF-8, ensure_ascii=false, separators comma/colon без пробелов.

SHA-256 accepted count payload: `a1cf13e231876712297a77b372456c31dce28d0b4adfb9f7acc1afe1e69c5ce1`.
SHA-256 accepted generation-shaped JSON: `e9a6b8e93f286ee786b7166540f33634e329a54ac64402da162eac5c19d0ddf5`.

### Итог этого запуска

**Все четыре обязательных count contracts PASS: 5 count calls, 0 generation calls, 0 history commits.** Current-only вызван ровно один раз. Два предыдущих исторических запуска сохранены выше: исходный baseline HTTP 400 и первый current-only timeout. Совокупно во всех трёх запусках выполнено 7 count calls и 0 generation calls.

Новый provider-count gate фактически пройден на этих fixtures. Это не доказывает generation context rejection и не закрывает настоящий overflow acceptance. Actual generation usage/cost отсутствуют; overflow execute не выполнялся. Application sessions/SQLite не создавались и не изменялись. Основная реализация не продолжена, architecture/planning artifacts и task checkboxes не менялись по указанию пользователя. Код, commit/push/archive отсутствуют; дальнейшая работа ожидает следующего сообщения пользователя.

## Integration через реализованный production adapter — 2026-09-09

Начало: **2026-09-09T18:04:42.844686+00:00**. Проверка выполнялась через
`OpenAIInputTokenCounter` и `OverflowPreparations.prepare`, с теми же synthetic
fixture texts из предыдущих запусков. Использован production timeout: **15 s,
connect 5 s**, SDK/application retries=0. Request hook подтвердил effective
connect/read/write/pool = 5/15/15/15 и разрешал только официальный input_tokens
endpoint. LLM dependency запрещала любую generation.

| Measurement | Provider input_tokens | Elapsed, s |
|---|---:|---:|
| Current-only | 19 | 2.487 |
| History-only | 35 | 0.637 |
| Full | 139 | 0.391 |
| Production overflow prepare | 139902 | 1.359 |

Overflow prepare выполнил два full count probes; accepted N=13975,
full payload=546130 bytes. Результат `prepared`, error=null, исходная test history
не изменилась. Synthetic user/assistant pair была предварительно явно записана
в отдельную временную SQLite fixture; oversized payload не commit'ился.
Пользовательские базы не открывались этим integration script.

Итого integration: **5 count calls, 0 generation calls**. Увеличение production
timeout до диагностических 60 секунд не потребовалось. Исторические smoke
сохранены выше. Эта проверка подтверждает counting/prepare, но не actual provider
generation overflow; execute и short/long generation автоматически не запускались.
