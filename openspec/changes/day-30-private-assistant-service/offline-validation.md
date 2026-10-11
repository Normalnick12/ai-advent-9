# Day 30 — offline validation, 2026-10-11

Windows, Python 3.14.7. Только синтетические fixtures и fake Ollama; настоящих
chat/embed/load calls не было. Tailscale, маршрутизатор и глобальная конфигурация
Ollama не изменялись. Это **offline technical PASS**, не live acceptance и не
семантическое подтверждение модели.

## Выполненные проверки

| Проверка | Фактический результат |
|---|---|
| Установка отдельных HTTP requirements | PASS, новый игнорируемый Day 30 `.venv` |
| CLI-only установка | PASS, отдельный `.local/day30-cli-venv`; FastAPI/Pydantic/Uvicorn отсутствуют |
| Core + Day 29 + Day 30 в HTTP environment | **414 passed, 1 skipped**, 7.11 s |
| Core + Day 29 в CLI-only environment | **349 passed, 1 skipped**, 4.94 s |
| Day 30 coverage в общем прогоне | 65 tests, все PASS |
| Два независимых TCP-клиента | admitted=2, max_active=2, completed=2, third=503, health=200 |
| Синтаксис / config / ссылка README | AST 24 Python files PASS, JSON PASS, root link/order PASS |
| `server.py --help`, `client.py --help` | PASS, в том числе клиент без HTTP framework |
| `pip check` обоих окружений | No broken requirements found |

Один skip — прежний POSIX FIFO test, неприменимый на Windows. Один warning в HTTP
прогоне — deprecation используемого Starlette TestClient/httpx backend; тесты и
реальный TCP test прошли. Проверенные HTTP версии: FastAPI 0.143.0, Pydantic 2.14.0,
Uvicorn 0.54.0, HTTPX 0.28.1, Starlette 1.7.0, pytest 9.1.1. Диапазоны requirements
не являются lock-файлом для всех будущих версий.

Повторение из корня repo (после установки по README; все запросы модели fake):

```powershell
Push-Location day-27-local-architecture-assistant
& ../day-30-private-assistant-service/.venv/Scripts/python.exe -B -m pytest tests ../day-29-local-assistant-optimization/tests ../day-30-private-assistant-service/tests -q -p no:cacheprovider
& ../.local/day30-cli-venv/Scripts/python.exe -B -m pytest tests ../day-29-local-assistant-optimization/tests -q -p no:cacheprovider
Pop-Location
& day-30-private-assistant-service/.venv/Scripts/python.exe -B -m pytest day-30-private-assistant-service/tests/test_service.py::test_two_real_tcp_connections_fake_ollama -q -s -p no:cacheprovider
```

CLI-only environment создан стандартным venv и установленными core requirements
плюс pytest. Existing backend environment не изменялся. Новые окружения исключены
из Git. Тесты не требуют запуска Ollama/старого backend/Android.

## Конкурентность, recovery и контекст

`test_two_real_tcp_connections_fake_ollama` запускает Uvicorn на временном loopback
порту и две независимые TCP-сессии. Барьер fake transport удерживает оба запроса
до проверки `active=2`, здоровья и третьего отказа с Retry-After. После снятия
барьера оба клиента получают 200, разные request_id и собственный результат.
Наблюдавшийся вывод: `TCP evidence: admitted=2 max_active=2 completed=2 third=503 health=200; fake inference only`.

Это доказательство HTTP concurrency и двух завершений с fake transport. Реальная
очередь Ollama, скорость GPU, два физических устройства и inference parallelism
**не проверялись**. Собственной очереди chat в приложении нет.

Управляемые тесты проверяют deadline, закрытие настоящего TCP-клиента, bounded
shutdown, занятый slot и fail-closed recovery. Late terminal completion снимает
неопределённость. ReadTimeout, malformed upstream или HTTP 500 без terminal
подтверждения оставляют recovery gate закрытым; отказ Ollama 503 не повторяется.
Readiness timeout сохраняет единственный probe, health/status не блокируются.

Настоящее контекстное уточнение: «А когда это разрешено?» без истории не находит
нужную документацию; после user-вопроса о Navigation находит текущий Markdown.
Подставленный assistant history не входит в retrieval query и не разрешает новую
цитату. Отдельно проверены combined query/terms, byte limits и неизменность прежнего
payload без истории. Семантику ответов fake transport оценивать нельзя.

## Безопасность и сохранность

- 401 до filesystem/upstream I/O; per-token buckets и refill с fake clock.
- Strict input fields, запрет role/system/tool/path/model, неизвестный file_id;
  исчезнувший allowlisted файл возвращает безопасный 404.
- Raw/chunked/no-length body, deadline тела, compression/media type, malformed JSON;
  bounded buffer, Unicode/history, полный prompt budget без скрытого обрезания.
- Текущие safe Workspace/Knowledge readers, stale/corrupt/missing index, links,
  Windows junction regression; никакого автоматического rebuild/fallback.
- Remote model/capability/digest mismatch отвергаются до generation; launcher
  проверен на loopback/один worker/no access log/no proxy headers.
- Canary markers приватных данных/вопросов/исключений не попадают в логи и ошибки;
  no-store, отключённые docs, безопасные unknown routes, отсутствие retry.
- Hashes временного корпуса до/после HTTP-диалога совпали; transcript не создаётся.

Baseline зафиксировал 867 уже существовавших файлов до работы. После реализации
859 SHA-256 совпали. Изменились только четыре согласованных core-файла
(`rag_cli.py`, `retrieval.py`, `grounded_explain.py`, `ollama_client.py`), корневой
README и три planning-артефакта Day 30 (design/spec/tasks). Новые common helpers
добавлены отдельно. Исторические fixtures/results/planning Days 27–29, весь Day 29
runtime и Weeks 1–5 сохранены. Никаких checkout/reset/clean/stage/commit/push/archive.

## Оставшиеся gates

OpenSpec: offline tasks 1–5 завершены, **25/33**. Sections 6–7 (**8 задач**) открыты.
OpenSpec strict validation: **PASS**, `Change 'day-30-private-assistant-service' is valid`.

Local live требует отдельного разрешения, synthetic corpus с настоящим свежим
индексом, проверки версии/digest/local-only/listeners и подготовки токенов. Если
индекса нет, отдельно разрешить embedding calls; исторические индексы не менять.
Основная серия: 2 calls вопрос/уточнение, затем 2 calls локальной конкурентной пары;
stop-on-error, без автоматических повторов. Done/stop/mechanical и semantic verdict
фиксировать раздельно. `semantic_status` API остаётся `not_evaluated`.

Tailscale требует отдельного подтверждения установки/настройки и remote live.
Затем Serve только к HTTP loopback, HTTPS/access policy, Bearer на втором устройстве
и 2 calls конкурентной пары с двух физических устройств, одно из другой сети.
Общий бюджет основной серии — 6 chat calls. Проверить выключение только Day 30
route. VPN не объявляется публичным hosting или однозначно одобренной автором
трактовкой внешнего IP. Mac M1 **NOT TESTED**; live/remote/video **PENDING**.
Coder 7B — технический кандидат; Day 29 **NO SUITABLE PROFILE CONFIRMED** неизменен.
