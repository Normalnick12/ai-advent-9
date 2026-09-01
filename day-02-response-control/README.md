# Day 02 — Response Control

## Цель

Один и тот же prompt отправляется с разным уровнем контроля, чтобы наглядно
сравнить свободный ответ модели и предсказуемый контракт для приложения.

- **FORMAT** — Structured Outputs задаёт строгую JSON Schema рецепта с обязательными
  полями, фиксированными типами и `additionalProperties: false`.
- **LENGTH** — необязательный `max_output_tokens` ограничивает ответ; статус
  `incomplete` и причина `max_output_tokens` отображаются без падения.
- **STOP** — современный Responses API получает явную developer instruction завершить
  ответ сразу после результата. Устаревший API и stop sequence не используются.

Structured Outputs выбран вместо prompt-only просьбы «ответь JSON», потому что схема
становится машинно проверяемым контрактом, а не пожеланием в естественном языке.

## Архитектура

```text
Android Compose
      |
      | POST /api/v1/generate
      v
FastAPI backend
      |
      | OPENAI_API_KEY (только здесь)
      v
OpenAI Responses API (gpt-5.6)
```

Android-проект находится в [`android-app/`](../android-app/README.md), backend — в
[`backend/`](../backend/README.md). Требуются Python 3.11+, Android Studio/JDK 17+
и Android SDK. Единственная секретная переменная — `OPENAI_API_KEY` на backend.

## Timeout budget

Android ждёт ответ backend до `190 с` (`read=180 с`). Backend ограничивает одну
попытку OpenAI `75 с` и разрешает максимум один retry. До исправления Retrofit
неявно использовал OkHttp `readTimeout=10 с`, тогда как OpenAI SDK ожидал до
`600 с` и мог сделать два retry. Поэтому нормальный ответ дольше 10 секунд
обрывался только на Android, особенно заметно в COMPARE с двумя параллельными
запросами. Backend теперь логирует `request_id`, длительность и отдельный
`openai_timeout`, не записывая prompt или секреты.

## Запуск

Backend:

```powershell
cd C:\Projects\ai-advent-9\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-key-here"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Затем откройте `C:\Projects\ai-advent-9\android-app` в Android Studio и запустите
`app` на Android Emulator.

Реализация следует актуальному механизму
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
и [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create).
