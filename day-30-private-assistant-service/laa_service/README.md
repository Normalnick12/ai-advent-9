# Необязательный HTTP-адаптер

Все команды ниже выполняются из корня репозитория в PowerShell 7. Нужен Python
3.12+ (shared Workspace reader использует `Path.is_junction`); фактически проверен
Windows/Python 3.14.7. Сервер не импортируется CLI и не запускается автоматически.
Основной CLI, Knowledge и Ollama остаются самостоятельными: см.
[инструкцию утилиты](../../day-27-local-architecture-assistant/README.md).

## Установка и offline-проверка

```powershell
py -3 -m venv day-30-private-assistant-service/.venv
& day-30-private-assistant-service/.venv/Scripts/python.exe -m pip install -r day-30-private-assistant-service/requirements-dev.txt
& day-30-private-assistant-service/.venv/Scripts/python.exe -B -m pytest day-30-private-assistant-service/tests -q -p no:cacheprovider
```

Для использования без тестов достаточно `requirements.txt`. Core requirements
по-прежнему содержат только httpx; FastAPI/Pydantic/Uvicorn устанавливаются отдельно.
Тесты используют временные синтетические данные, fake embeddings/Ollama и запрещают
реальный HTTPX transport. TCP integration поднимает только временный loopback
listener. Настоящая Ollama, backend предыдущих недель и Android не нужны.

## Конфигурация владельца

Скопируйте [пример](../config.example.json) в игнорируемый `.local/day30/config.json`.
Пример намеренно не готов к запуску: требуется реальный digest и подтверждение
local-only. Относительные пути считаются от рабочего каталога запуска, не от JSON.

- `workspace`: отдельный локальный каталог с разрешёнными синтетическими `.kt`.
- `knowledge`: отдельный локальный каталог с синтетическими Markdown и уже
  подготовленным свежим индексом Day 28. HTTP не создаёт и не обновляет индекс.
  Создание настоящего индекса вызывает embeddings и требует отдельного live-разрешения.
- `files`: отображение непрозрачного ID (например, `demo`) в относительный Kotlin
  path. Клиент получает ID от владельца, endpoint списка файлов отсутствует.
- `token_env`: безопасные labels → имена переменных окружения с отдельными токенами
  устройств; не сами секреты. 1–16 уникальных URL-safe токенов длиной 43–128 символов.
- `digest`: точный установленный digest `qwen2.5-coder:7b-instruct-q4_K_M`.
  Тег, retrieval=text, top_k=4 и профиль 8192/2048 фиксированы сервером.
- `base_url`: только `http://127.0.0.1:11434` (другой локальный порт допустим).
- `local_only_confirmed=true`: подтверждение владельцем отключённых cloud features
  Ollama и loopback listener; это декларация, а не автоматический аудит настроек ОС.
  Metadata дополнительно отвергает remote model и неожиданный digest на каждом ходе.

Настоящий preflight и model calls в offline-этап не входят. После отдельного
разрешения проверить loopback binding Ollama, cloud-disabled режим установленной
версии и digest. Для ограниченной демонстрации операторский профиль:
`OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_QUEUE=2`, `OLLAMA_MAX_LOADED_MODELS=1`.
Сервис эти глобальные настройки не применяет. CLI inference и чужие эксперименты
не запускать одновременно с live-приёмкой. Переключение parallel=2 не требуется.

Токены можно сгенерировать в памяти, не выводя их в терминал или файл:

```powershell
$env:LAA_TOKEN_A = & day-30-private-assistant-service/.venv/Scripts/python.exe -c 'import secrets; print(secrets.token_urlsafe(32))'
$env:LAA_TOKEN_B = & day-30-private-assistant-service/.venv/Scripts/python.exe -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Передать отдельный токен второму устройству защищённым способом. Не помещать его
в Git, JSON, URL, shell arguments или журналы. Для ввода существующего токена без
записи значения в историю команд PowerShell: `Read-Host -AsSecureString`, затем
преобразование только в переменную процесса, например:

```powershell
$day30Secret = Read-Host 'Bearer token' -AsSecureString
$env:LAA_CLIENT_TOKEN = [System.Net.NetworkCredential]::new('', $day30Secret).Password
Remove-Variable day30Secret
```

## Локальный запуск и клиент

После подготовки конфигурации и явного разрешения соответствующих live-проверок:

```powershell
& day-30-private-assistant-service/.venv/Scripts/python.exe -B day-30-private-assistant-service/server.py --config .local/day30/config.json
```

Один процесс, один worker, `127.0.0.1:8030`, без reload, autostart, reverse proxy
headers и access log. Можно поменять только порт через `--port`. Запуск ничего
не загружает в модель и не строит индекс. Использовать этот launcher, а не прямой
Uvicorn CLI с другим bind/workers/logging.

В отдельном терминале задайте `LAA_CLIENT_TOKEN` и запустите:

```powershell
& day-30-private-assistant-service/.venv/Scripts/python.exe -B day-30-private-assistant-service/client.py --file-id demo
```

Вопросы вводятся через stdin; `/reset`, `/file ID`, `/quit`. История только в RAM,
не более двух полных пар и 8 KiB compact UTF-8 JSON. Клиент удаляет старые целые
пары с уведомлением; при ошибке не добавляет неуспешный ход. Reset, смена файла и
выход очищают историю. Терминал показывает ответ для review; не включайте transcript
или перенаправление stdout для приватных данных.

Минимальный независимый вызов (сам `POST /v1/chat` запускает inference):

```powershell
$day30Headers = @{ Authorization = "Bearer $env:LAA_CLIENT_TOKEN" }
Invoke-RestMethod http://127.0.0.1:8030/healthz
Invoke-RestMethod http://127.0.0.1:8030/readyz -Headers $day30Headers
Invoke-RestMethod http://127.0.0.1:8030/v1/status -Headers $day30Headers
$day30Body = @{ file_id = 'demo'; question = 'Когда разрешена навигация?'; history = @() } | ConvertTo-Json -Depth 5 -Compress
Invoke-RestMethod http://127.0.0.1:8030/v1/chat -Method Post -Headers $day30Headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($day30Body))
```

## HTTP-контракт

| Endpoint | Авторизация | Смысл |
|---|---|---|
| `GET /healthz` | Нет | Только HTTP liveness, `{"status":"ok"}`, без data/model I/O |
| `GET /readyz` | Bearer | Свежесть данных и metadata/digest модели, 200/503; без inference, cache ≤5 s |
| `GET /v1/status` | Bearer | Cached ready, active/limit/max_active, recovery_required, profile, limits |
| `POST /v1/chat` | Bearer | Один независимо проверяемый ход; ответ целиком после окончания |

Тело chat: `{"file_id":"demo","question":"А когда это разрешено?","history":[{"user":"Когда разрешена навигация?","assistant":"Предыдущий ответ"}]}`.
Другие поля и system/tool/role messages запрещены. История не является доказательством.
Поиск детерминированно объединяет текущий вопрос, последний user-вопрос и filename;
assistant history в query не входит. Новые citations проверяются только по текущему
Kotlin и реально выбранным Markdown chunks. Сервер не хранит сессии.

Успешный envelope: `request_id`, `result` (прежняя grounded schema), `sources`
(chunk_id/относительный source/section/start_line/end_line), `metrics`,
`mechanical_validation=passed`, `semantic_status=not_evaluated`.
Проверяются done/stop, schema, IDs, диапазоны строк и точные цитаты. Это не проверка
истинности выводов модели. Возвращаемые источники и цитаты доступны каждому
авторизованному клиенту общего корпуса; отдельных per-file ACL для разных tokens нет.

Ошибки содержат только `error.code`, фиксированное `error.message`, `request_id`.
Все ответы `Cache-Control: no-store`. Основные коды:

| HTTP | Code |
|---|---|
| 401 / 404 | unauthenticated / file_not_found или not_found |
| 413 / 415 | request_too_large / unsupported_media_type |
| 422 | invalid_request / context_budget_exceeded |
| 429 | rate_limited, Retry-After |
| 502 | invalid_model_response, без raw/частичного ответа |
| 503 | capacity_exceeded (Retry-After), upstream_overloaded, upstream_unavailable, knowledge_unavailable, recovery_required |
| 504 / 500 | request_timeout или body_timeout / internal_error |

## Ограничения и ownership

| Ограничение | Значение |
|---|---|
| Chat token bucket | Пополнение 6/min, burst 2 на token |
| Ready/status общий bucket | Пополнение 30/min, burst 5 на token |
| Допущенные chat | 2 на процесс; третий немедленно 503, если не исчерпан rate bucket |
| Raw body / получение body | 32 KiB / 10 s, фактический поток также ограничен |
| Вопрос / последний user-вопрос | По 2000 Unicode code points |
| History | 2 пары, 8192 bytes compact JSON с неэкранированным Unicode |
| Retrieval query | 4096 символов, 64 уникальных literal terms |
| Kotlin / полный Ollama request / response | 16 KiB / 24 KiB / 256 KiB |
| num_ctx / num_predict | 8192 / 2048, нельзя переопределить клиентом |
| Chat deadline / connect / I/O | 120 s абсолютного ожидания / 3 s / 120 s |
| Readiness | 5 s ожидание, metadata I/O 2 s; один probe worker |
| Клиент / Uvicorn connections | HTTPX timeout 135 s / максимум 32 concurrent tasks/connections |

Byte budget не доказывает полный token fit. Вопрос/история/исходник не обрезаются:
слишком большой обязательный контекст отвергается; целые chunks добавляются по
рангу, selected/omitted отражают фактический набор. Текстовый поиск Day 30 не вызывает
query embeddings; свежий существующий SQLite index всё равно обязателен.

Синхронный общий runtime выполняется в двух worker threads, health/status обслуживает
event loop. Собственной очереди ожидающих chat, scheduler или persistent jobs нет;
ожидание модели передаётся штатной Ollama. Одновременный HTTP не доказывает GPU parallelism.

Deadline/disconnect заканчивает ожидание клиента, **не останавливает Ollama**. Slot
остаётся за фактической операцией. При неизвестном исходе отправленного inference
`recovery_required=true`, новые chat получают 503. Поздний подтверждённый terminal
ответ может освободить slot. Если transport завершился без подтверждения, gate
остаётся закрыт: не retry и не ожидание фиксированной паузы. Оператор сначала
проверяет/восстанавливает Ollama (при необходимости отдельно разрешённый restart),
затем перезапускает HTTP. Простого restart HTTP или наличия модели в `ollama ps`
недостаточно для доказательства завершения. Автоматического recovery endpoint нет.

## Приватность и остановка

В HTTP logs только UUID request_id, фиксированная route category, status, elapsed,
active и recovery. Ни headers/raw URL, ни вопросы/история/ответы/исходники/цитаты,
ни исключения с путями не журналируются. Debug/docs/OpenAPI/access logs выключены;
HTTPX не использует proxy environment, redirects и retries. Ошибки validation не
возвращают submitted input. Приложение не меняет Workspace/Knowledge/index.
Launcher сохраняет собственную logging policy через `log_config=None`: записи
HTTPX/HTTPCore и их дочерних логгеров поглощаются `NullHandler` без propagation,
access logger отключён. Безопасные `laa.http` метрики и lifecycle сервера остаются.
Файлы принадлежат доверенному локальному владельцу; защита от одновременно
враждебно меняющего файловую систему локального процесса вне модели угроз.

Остановить HTTP: Ctrl+C в его терминале. При спокойном состоянии CLI и Ollama
продолжают работать, данные и модели не удаляются. При незавершённой работе launcher
ограничивает graceful ожидание HTTP 5 секундами, service.close — ещё 5 секундами.
Это не обещание завершения процесса/runner за 5 s: Python может ждать worker threads
с конечными I/O timeout. Не завершать чужие процессы. Проверить safe recovery status
и неизвестный исход перед новым запуском. Для отзыва токена удалить/заменить его
в environment/config и перезапустить только HTTP; сессий для удаления нет.

## Второе устройство — отдельный этап

Установка/настройка Tailscale и live remote пока не разрешены и не выполнялись.
После отдельного подтверждения: два устройства в разрешённой tailnet, HTTPS Serve
только к `http://127.0.0.1:8030`, минимальная access policy для выбранных peers/порта.
Не публиковать Ollama 11434 или каталоги. Bearer auth сохраняется поверх HTTPS.
Проверить отсутствие content/Authorization в proxy logs; сертификаты проверяются,
опции `-k`/verify=false запрещены. Реальные настройки и точная команда Serve будут
сверены с установленной версией в этом отдельном этапе.

На втором устройстве достаточно Python, checkout с day27/day30 и core httpx
requirements; FastAPI нужен только серверу. Запустить `client.py --url
https://<разрешённое-имя-в-tailnet> --file-id demo` с `LAA_CLIENT_TOKEN` в environment.
Для другой ОС заменить путь к Python; Mac фактически не проверялся. Альтернатива —
тот же Bearer JSON POST обычным HTTPS-клиентом. Android/web UI не требуется.

Демонстрация: два физических устройства, одно в другой сети через интернет,
одновременно отправляют по одному синтетическому запросу. Зафиксировать два
request_id, перекрытие HTTP и два успешных завершения; время очереди/параллелизм
runner без прямого измерения помечать unavailable/not confirmed. После демонстрации
удалить только созданный Day 30 Serve route и проверить его недоступность; не делать
глобальный reset чужих маршрутов. CLI/данные/Ollama сохраняются.

Это приватный доступ через интернет, не публичный hosting. Автор челленджа явно
не подтверждал VPN как трактовку «внешнего IP». VPS, public IP, port forwarding и
Funnel здесь не реализуются и не требуются для localhost функциональности.
