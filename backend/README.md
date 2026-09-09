# Backend

Локальный FastAPI-сервис для Android-приложения. Принимает запросы, обращается
к OpenAI Responses API и возвращает ответы с метриками. Поддерживает управление
форматом и длиной ответа, сравнение prompting-стратегий, значений temperature и моделей.
API-ключ используется только на сервере.

[Day 05](../day-05-model-benchmark/README.md): каталог доступен через
GET /api/v1/model-benchmark/catalog; POST /api/v1/model-benchmark/run принимает
три выбранных model id и возвращает независимую проверку пяти задач и метрики.
Каталог не требует ключа. Запуск делает по одному вызову на слот без retries.

[Day 06 — первый агент](../day-06-first-agent/README.md) добавляет изолированные
диалоги: POST `/api/v1/agent/sessions` с `{}`, POST
`/api/v1/agent/sessions/{session_id}/messages` с `{"message":"текст"}` и DELETE
`/api/v1/agent/sessions/{session_id}`. SimpleAgent передаёт полную историю явно
через отдельный OpenAIResponsesLlmClient. История и фиксированные настройки
остаются на сервере; клиент получает текущий ответ и число завершённых ходов.
[Day 07 — сохранение контекста](../day-07-context-persistence/README.md) развивает
тот же Agent subsystem: SQLite — источник сохранённой истории, AgentSession —
восстановимый снимок в RAM. Успешная пара user/assistant сначала фиксируется
одной транзакцией, затем обновляет RAM; ошибка записи не продвигает историю.
После restart mapping пустой, известный ID лениво восстанавливается из SQLite.
GET `/api/v1/agent/sessions/{session_id}` возвращает только `session_id` и
`history_turn_count`. Create/GET/delete не требуют ключа и не вызывают OpenAI.
Неизвестный ID даёт 404, одновременный turn/GET/delete занятой session — 409.
DELETE сначала надёжно удаляет историю, затем закрывает runtime session;
повторное удаление корректного ID возвращает 204.

Запускайте **один worker**: busy защищает session внутри одного процесса.
Стандартный Python `sqlite3` выполняет короткие синхронные операции в том же
потоке; connection открывается/закрывается в lifespan. Явные BEGIN/COMMIT/ROLLBACK,
foreign keys и обычный rollback journal обеспечивают атомарную запись пары.
База `.local/agent/conversations.sqlite3` находится относительно корня проекта,
независимо от shell cwd; файл и sidecars уже исключены из Git. Первый запуск
создаёт schema. История старого RAM-only процесса Day 06 не переносится.
Restart не очищает SQLite; используйте «Новый диалог» для явного удаления.
Busy, locks и незавершённые запросы не сохраняются. Семантической памяти,
сжатия истории, ORM, автоматического TTL и восстановления UI transcript нет.

## Требования

Python 3.11+, зависимости из [requirements.txt](requirements.txt)
и переменная окружения `OPENAI_API_KEY`. Для общего скрипта запуска нужен PowerShell 7.

## Подготовка

Из корня репозитория в PowerShell 7, один раз:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..
```

Создайте локальный игнорируемый `backend/.env` с `OPENAI_API_KEY`
или задайте эту переменную в терминале. Не сохраняйте ключ в исходниках или Git.

## Запуск

Из корня репозитория:

```powershell
.\scripts\dev.ps1 backend
```

Скрипт использует `backend/.venv`, автоматически загружает `backend/.env`,
если он существует, и не запускает второй сервер на занятом порту `8000`.
Сервер работает в текущем терминале, здесь же доступны логи; остановка — Ctrl+C.
После изменения backend перезапустите его: автоматическая перезагрузка не включена.

В другом терминале выполните `.\scripts\dev.ps1 status` для проверки готовности.
После запуска доступны [Swagger UI](http://127.0.0.1:8000/docs)
и [проверка состояния](http://127.0.0.1:8000/health).
`/health` проверяет FastAPI, но не доступность OpenAI.
Подключение клиента описано в [Android README](../android-app/README.md),
работа с процессами и диагностика — в [окружении Windows](../scripts/README.md).

## Тесты

Из папки `backend` с активированным окружением:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

Persistence-тесты открывают отдельные реальные SQLite-файлы в `tmp_path`,
закрывают старые store/manager и восстанавливают history новым экземпляром.
Пользовательская `.local` БД в pytest не открывается. Fake LLM проверяет точный
контекст U1/A1/U2; fault injection проверяет rollback и ошибки commit.
Живой restart обоих процессов проверяется отдельно, после завершённого ответа;
потеря HTTP-ответа или crash посреди неопределённого turn вне гарантии Day 07.


## Day 08 — токены

`/api/v1/token-lab/sessions` предоставляет отдельные create/GET/delete и
`/{id}/messages` с тем же message limit 20000. Day 08 использует второй instance
того же SimpleAgent: immutable `day08-gpt4o-mini-v1`, `gpt-4o-mini`,
reasoning omitted, output budget 1200, Standard tier, truncation disabled.
Отдельный manager и файл
`.local/token-lab/day08-gpt4o-mini-v1/conversations.sqlite3` используют прежнюю
schema sessions/messages. Одинаковые resolved DB paths блокируют startup.
Identity — namespace + UUID; чужие get/send/prepare/execute дают 404, cross-delete
безопасен. Metadata lifecycle не вызывает OpenAI. SQLite не хранит tokens/cost.

Normal Send выполняет current-only count, history-only count (пустая history=0
без запроса), full count с instructions, затем максимум одну generation.
Counts относятся к одному immutable snapshot до commit и неаддитивны.
Основная context utilization — full preflight/128000; reserve 1200 показывается
отдельно. Timeout count: 15 секунд, connect 5; normal preflight deadline 45,
generation deadline 75. SDK/application retries=0. Существующие Day 06/07
не выполняют count calls и сохраняют прежние generation payload/HTTP DTO.

Result возвращает outcome/attempt ID, committed count, diagnostics, nullable
usage/model/tier и estimated cost. Ни history, ни instructions не возвращаются.
Pricing использует Decimal и actual input/cached/output по rates
0.15/0.075/0.60 USD/MTok, проверенным 2026-09-09; источник приходит в response.
Reasoning входит в output, cache writes без отдельной надбавки.
Unknown model/tier, missing или inconsistent usage дают unavailable; pricing
failure не отменяет пригодный completed turn. Day 05 pricing не изменён.

`POST /{id}/overflow/prepare` с `{}` выполняет только counts: максимум четыре
full probes к target 140000, accepted 132000–160000, полный JSON <=2 MiB.
Это resource cap, не model limit. Рецепт/образцы/digest/размеры видны клиенту;
standalone current/history для probe не считаются. Подготовка хранится только
в RAM 10 минут, одна на session, максимум 16. Новый prepare, успешный normal
commit/reset или restart инвалидирует старое разрешение.

`POST /{id}/overflow/execute` принимает только
`{"preparation_id":"…","confirm":true}` после отдельного подтверждения.
Session/history/config/digest/expiry проверяются, ID потребляется до generation.
Probe никогда не commit'ится, даже при unexpected provider acceptance.
Только structured generation `context_length_exceeded` считается доказательством
переполнения; count rejection, 400 без этого code, 413/429/timeout — другие исходы.
Не повторяйте execute после unknown response: проверьте доступность/count через
GET, затем обычный turn допустим; это не подтверждение отсутствия расходов.

[Фактический provider-count smoke](../openspec/changes/archive/2026-09-09-day-08-token-lab/provider-count-smoke.md)
сохраняет первоначальный failed baseline, transient timeout и успешную проверку
новой схемы. Offline pytest использует mocks и временные SQLite-файлы, а не
платную generation. Реальный short/long/overflow acceptance выполняется отдельно
из Android; один live overflow требует отдельного явного подтверждения.
