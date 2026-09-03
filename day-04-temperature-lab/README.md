# Day 04 — Temperature Lab

Лаборатория в существующих `android-app` и `backend` сравнивает один и тот же
запрос при `temperature = 0 / 0.7 / 1.2`. Единственная переменная внутри одного
batch — temperature. Day 02 и Day 03 остаются отдельными экранами.

## Фиксированные параметры

| Параметр | Значение |
|---|---|
| model | `gpt-5.6` |
| reasoning | `effort=none`, `mode=standard` |
| max_output_tokens | `600` |
| top_p | Не передаётся, используется default API |
| store | `false` |
| prompt_cache_options | `mode=explicit` (без implicit cache) |
| retries | `0` |
| timeout | Connect: 5 секунд; остальные операции: 75 секунд |

Prompt, reasoning, output contract и все остальные отправленные параметры
одинаковы для трёх вызовов. Сервис не подменяет модель, effort, temperature или
формат при ошибке. Вызовы конкурентные; задержка измеряется отдельно через
monotonic clock. По одному значению задержки нельзя делать вывод о temperature.

## Режимы и проверка

Canonical benchmark предлагает придумать пять названий приложения подготовки
разработчиков к техническим собеседованиям и короткие слоганы. Его полный текст
находится в `backend/app/temperature_domain.py` и предзаполнен в Android.

Benchmark включается только при **точном** совпадении prompt, включая пробелы и
переносы строк. Strict Structured Output задаёт объект
`{"variants": [{"name": "…", "slogan": "…"}]}` без `minItems`, `maxItems` и
`uniqueItems`: число вариантов проверяет код, а не schema.

Backend независимо от LLM проверяет пять критериев:

1. Ровно пять вариантов.
2. Каждое название содержит 1–2 слова (разделение по whitespace).
3. Названия уникальны после trim/collapse whitespace/casefold.
4. Нет отдельных слов Interview, AI, ИИ без учёта регистра; пунктуация отделяет
   слова, вхождения внутри более длинного слова разрешены.
5. Каждый слоган содержит не более восьми whitespace-слов.

UI показывает «Соблюдение требований: N/5». При непроверенном/ошибочном ответе
validation отсутствует, это не `0/5`. Семантическая уместность и креативность
оцениваются человеком: Creativity Score, accuracy score и LLM-as-a-judge нет.

Любая правка canonical prompt включает свободный режим. Пользовательский текст
передаётся неизменным всем трём вызовам, используется обычный text response.
Автопроверка benchmark и секция уникальных названий отключены; показано явное
предупреждение. «Вернуть benchmark» восстанавливает точный исходный текст.

## Архитектура и session state

- `backend/app/temperature_domain.py`: canonical prompt, mode, pure validator.
- `temperature_models.py`: строгие Pydantic контракты.
- `temperature_service.py`: общий envelope, три параллельных вызова, usage,
  latency и безопасные per-temperature ошибки.
- `POST /api/v1/temperature-lab/run`: только `{"prompt": "…"}`; response содержит
  request id, mode, read-only config и три результата в порядке 0 / 0.7 / 1.2.
- Android: DTO → Retrofit repository → constructor-injected ViewModel → Compose.

История хранит максимум три newest-first batch текущего точного prompt только
в памяти ViewModel. При редактировании предыдущий scope скрывается; после batch
другого prompt он заменяется. Transport failure не стирает предыдущую историю.
Перезапуск процесса очищает историю; Room/DataStore не используются.

«Уникальные названия» — exact normalized unique names / total generated,
раздельно для каждой temperature. Android использует нормализованные имена,
вычисленные backend. Накопители живут всю сессию, не ограничены тремя history
записями и не изменяются свободными запросами. Это наблюдаемое разнообразие,
не оценка качества или креативности.

## Окружение и запуск

Нужны Python 3.11+, JDK 17 (проверено также с JDK 21), Android SDK 36,
Android Studio/Gradle wrapper и Android Emulator API 26+. API-ключ нужен только
backend; Android обращается к `http://10.0.2.2:8000/`.

Из корня репозитория, PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Создайте локальный ignored `backend/.env` с переменной `OPENAI_API_KEY`.
Не добавляйте этот файл или реальный ключ в Git. Существующее окружение можно
использовать повторно, создавать virtualenv заново не требуется.

```powershell
# Из backend; --env-file читает локальный секрет, не выводя его значение.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --env-file .env --host 0.0.0.0 --port 8000
```

Health: `http://127.0.0.1:8000/health`, Swagger: `http://127.0.0.1:8000/docs`.
Во втором терминале:

```powershell
cd android-app
.\gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=1 --no-configuration-cache
android emulator start Pixel_3a_API_34_extension_level_7_x86_64
android run --device=emulator-5554 --activity=com.example.responsecontrollab.MainActivity --apks=app\build\outputs\apk\debug\app-debug.apk
```

Имя AVD и serial замените на свои (`android emulator list`). Не добавляйте
`--debug` к `android run`: он включает ожидание подключения отладчика. Альтернатива:
открыть `android-app` в Android Studio и запустить конфигурацию `app`.

## Live compatibility gate 1.1

Probe выполнен 2026-09-03 до production-изменений, OpenAI SDK 2.54.0.
Все три точных benchmark-вызова приняты и strict shape разобран. Запрошена
`gpt-5.6`, ответ API указал resolved model `gpt-5.6-sol` (подмена в клиенте не
выполнялась). `top_p` omitted, envelopes равны после удаления temperature.

| temperature | status | total tokens | latency, мс |
|---|---|---:|---:|
| 0 | completed | 327 | 5580 |
| 0.7 | completed | 341 | 2995 |
| 1.2 | completed | 326 | 3374 |

Fallback не использовался. Эти значения — результат одного probe, не вывод о
качестве модели или скорости при разных temperatures.

## Проверки

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
cd ..\android-app
.\gradlew.bat testDebugUnitTest assembleDebug --console=plain --no-daemon --max-workers=1 --no-configuration-cache
```

Проверены backend domain/contracts/envelopes/errors/concurrency/endpoints и
регрессия Day 02/03; Android serialization/repository/ViewModel/history/unique
accumulators. Unit tests не требуют OpenAI или ключа. Итог: 57 backend tests и 23 Android
unit tests прошли, `assembleDebug` успешен.

На Pixel 3a API 34 проведён live smoke: canonical batch (три completed, 5/5),
free text batch, раскрытие ответов, read-only параметры, уникальные имена 5/5
по каждой temperature, замена prompt scope и история из трёх последних после
четырёх free runs. В четвёртом free batch были connect timeout-ошибки OpenAI:
карточки корректно сохранились без ложной benchmark-оценки и без fallback/retry.
Навигация Day 02/03 осталась доступной.

## Ручная end-to-end проверка

1. Запустите backend с `.env` и Android app, откройте «Лаборатория температуры».
2. **Benchmark:** нажмите «Вернуть benchmark», затем «Запустить сравнение».
   Дождитесь трёх карточек 0 / 0.7 / 1.2. Проверьте status, «Соблюдение
   требований: N/5», входные/выходные/рассуждающие/общие tokens и отдельную
   задержку. Раскройте и скройте ответы всех карточек.
3. Раскройте «Параметры эксперимента»: model `gpt-5.6`, none/standard, 600,
   default top_p и «Меняется только temperature». Редактируемых controls нет.
4. **История:** выполните ещё три запуска с тем же prompt. В истории должны
   остаться только последние три, newest-first. Измените хотя бы один символ:
   старая история и результаты скроются. После запуска новая история содержит
   только новый prompt. Перезапустите процесс приложения — история пуста.
5. **Уникальные названия:** в benchmark сравните `unique / total` каждой
   temperature после нескольких запусков. Повтор normalized name увеличивает
   только total; другая temperature имеет независимый набор. Четвёртый run
   продолжает накопление, несмотря на eviction старой history-записи.
6. **Free prompt:** замените текст, например на «Назови три цвета», и запустите.
   Проверьте предупреждение об отсутствии автопроверки, три обычных текстовых
   ответа, tokens/latency, отсутствие N/5 и секции уникальных названий.
   «Вернуть benchmark» возвращает исходный режим; session-счётчики benchmark
   сохраняются, но история другого prompt не смешивается.
7. Откройте Day 02 и Day 03 через нижнюю навигацию. При остановленном backend
   проверьте русское сообщение об ошибке; предыдущая история не должна исчезнуть.

При медленном эмуляторе можно отключить `window_animation_scale`,
`transition_animation_scale` и `animator_duration_scale` через ADB (`0`;
для восстановления — `1`).
