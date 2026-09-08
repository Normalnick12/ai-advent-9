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
