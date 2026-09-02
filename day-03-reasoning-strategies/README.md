# День 3 — Reasoning Lab

Учебный эксперимент сравнивает четыре prompting-стратегии на одной фиксированной
задаче оптимизации. Качество оценивает не другая LLM, а детерминированный полный
перебор и verifier backend.

## Что сравнивается

- `DIRECT` — «Прямой ответ», один вызов;
- `STEP_BY_STEP` — «Пошаговое решение», один вызов;
- `META_PROMPT` — «Мета-промпт», генерация инструкции и затем решение, два вызова;
- `EXPERT_PANEL` — «Группа экспертов», один role-prompted вызов без subagents.

Для всех вызовов зафиксированы модель `gpt-5.6`, standard reasoning mode,
`reasoning.effort=medium`, `max_output_tokens=1200`, `store=false`, explicit
prompt-cache mode, timeout 75 секунд и нулевое число SDK retries. Все финальные
вызовы получают один канонический текст задачи и одну strict Structured Output
schema.

## Фиксированная задача и эталон

Лимит — 15 story points. Фичи: A `(4, 8)`, B `(6, 11)`, C `(5, 10)`,
D `(3, 6)`, E `(7, 13)`, F `(2, 4)`, G `(4, 7)`, H `(5, 8)`, где пара —
`(стоимость, ценность)`.

Ограничения:

- B несовместима с E;
- C допустима только вместе с F;
- A несовместима с D;
- G несовместима с H;
- суммарная стоимость не превышает 15.

Полный перебор `2^8` множеств даёт единственный оптимум: A + C + F + G,
стоимость 15, ценность 29. Verifier отдельно пересчитывает ограничения и итоги,
отвергает дубликаты, неизвестные id и несовпадающие заявленные суммы.

## Архитектура

Android-клиент вызывает только локальный FastAPI endpoint
`POST /api/v1/reasoning-lab/run`. Backend параллельно запускает четыре pipeline;
два META_PROMPT-вызова внутри одного pipeline остаются последовательными. Ошибка
одной стратегии превращается в её typed result и не удаляет остальные карточки.
`OPENAI_API_KEY` существует только в окружении backend.

## Подготовка backend

Требуются Python 3.11+ и Android SDK/Studio для клиента. В PowerShell:

```powershell
cd C:\Projects\ai-advent-9\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
$env:OPENAI_API_KEY = "<your-openai-api-key>"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Подставляйте ключ только в локальную переменную окружения. Не записывайте его в
README, `.env`, исходники или Android-конфигурацию.

Проверка backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health

$body = @{} | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/reasoning-lab/run `
  -ContentType "application/json" `
  -Body $body
```

Ответ содержит `request_id`, фиксированную конфигурацию, эталон и результаты в
порядке DIRECT, STEP_BY_STEP, META_PROMPT, EXPERT_PANEL.

## Запуск Android

1. Откройте `C:\Projects\ai-advent-9\android-app` в Android Studio.
2. Выберите JDK 17+ и дождитесь Gradle Sync.
3. Запустите Android Emulator; backend должен продолжать слушать
   `0.0.0.0:8000`.
4. Запустите конфигурацию `app`.
5. В нижней навигации выберите «Лаборатория рассуждений».
6. Нажмите «Запустить все стратегии» один раз.

Emulator обращается к host-машине по `http://10.0.2.2:8000/`. API-ключ в
Android не вводится и не передаётся.

## Ручная end-to-end проверка

После завершения batch:

1. Убедитесь, что видны четыре карточки: «Прямой ответ», «Пошаговое решение»,
   «Мета-промпт», «Группа экспертов».
2. Прокрутите экран и проверьте в каждой карточке выбранные фичи, стоимость,
   ценность, объяснение, задержку, token usage и число API-вызовов.
3. Для корректного результата A + C + F + G ожидаются стоимость 15, ценность 29
   и заметный статус «Правильно».
4. У DIRECT, STEP_BY_STEP и EXPERT_PANEL ожидается «Вызовов API: 1», у
   META_PROMPT — «Вызовов API: 2».
5. Только в карточке «Мета-промпт» нажмите «Показать сгенерированный промпт»,
   прокрутите/выделите текст, затем нажмите «Скрыть сгенерированный промпт».
6. Перейдите в «Управление ответом» и обратно, чтобы проверить сохранение
   доступа к экрану Day 02.
7. Если одна стратегия получила rate-limit/timeout, убедитесь, что её ошибка
   находится в собственной карточке, а успешные карточки сохранены; затем при
   необходимости явно повторите весь batch кнопкой.

## Автоматические проверки

Backend не требует живого OpenAI-вызова:

```powershell
cd C:\Projects\ai-advent-9\backend
python -m pytest
```

Android:

```powershell
cd C:\Projects\ai-advent-9\android-app
.\gradlew.bat testDebugUnitTest assembleDebug
.\gradlew.bat connectedDebugAndroidTest
```

Последняя команда требует запущенный emulator. Unit и API tests используют fake
repository/mocked Responses API и не расходуют OpenAI quota.
