# Response Control Lab backend

Локальный FastAPI backend для Day 02. Он принимает prompt и независимые controls,
вызывает OpenAI Responses API на модели `gpt-5.6` и возвращает единый контракт для
Android-клиента. API-ключ используется только здесь.

Backend также обслуживает
[Day 03 Reasoning Lab](../day-03-reasoning-strategies/README.md) через
`POST /api/v1/reasoning-lab/run`. Endpoint запускает четыре стратегии на одной
фиксированной задаче и возвращает частичные результаты, если отдельный OpenAI
вызов завершился ошибкой.

## Зависимости и окружение

- Python 3.11+;
- переменная окружения `OPENAI_API_KEY`;
- пакеты из `requirements.txt`.

Windows PowerShell:

```powershell
cd C:\Projects\ai-advent-9\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-key-here"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Не записывайте реальный ключ в `.env.example`, README или исходный код.

## Пример запроса

```powershell
$body = @{
  prompt = "Составь рецепт греческого салата."
  controls = @{
    structured_output = $true
    max_output_tokens = 600
    finish_instruction = $true
  }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/generate `
  -ContentType "application/json" `
  -Body $body
```

Swagger UI доступен по адресу `http://127.0.0.1:8000/docs`, health check —
`http://127.0.0.1:8000/health`.

Reasoning Lab принимает строгий пустой объект:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/reasoning-lab/run `
  -ContentType "application/json" `
  -Body '{}'
```

## Timeout и диагностика

- OpenAI SDK: connect timeout `5 с`, остальные операции `75 с` на попытку;
- OpenAI SDK: не более одного автоматического retry (`max_retries=1`);
- каждый вызов получает `request_id`, который возвращается в JSON и заголовке
  `X-Request-ID`;
- Uvicorn пишет начало, длительность и результат вызова без prompt и секретов;
- timeout OpenAI возвращается отдельно как `error.code = openai_timeout`.

Значения также видны в `GET /health`. Uvicorn `timeout_keep_alive=5` оставлен без
изменений: он действует между запросами и не ограничивает время выполнения endpoint.
Для более подробной диагностики самого SDK можно временно запустить backend с
`$env:OPENAI_LOG = "info"`.

Retry-настройки выше относятся к Day 02. Reasoning Lab использует тот же timeout
75 секунд, но `max_retries=0`; META_PROMPT выполняет не более двух
последовательных вызовов. Prompt и generated prompt не записываются в application
logs.

## Проверки

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Day 04 Temperature Lab

[README Day 04](../day-04-temperature-lab/README.md) — точка входа для лаборатории.
`POST /api/v1/temperature-lab/run` принимает только `{"prompt":"…"}`. Три
конкурентных вызова отличаются только temperature (0 / 0.7 / 1.2): none/standard,
600 tokens, default top_p, zero retries. Benchmark получает strict variants и
пять formal checks; произвольный prompt — обычный текст без benchmark-оценки.
Для локального `.env` используйте `uvicorn ... --env-file .env`.
