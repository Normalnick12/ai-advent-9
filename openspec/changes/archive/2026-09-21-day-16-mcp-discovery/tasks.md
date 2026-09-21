## 1. Standalone experiment setup

- [x] 1.1 Создать `day-16-mcp-discovery/main.py`, `requirements.txt` с `mcp==2.2.0` и `requirements-dev.txt` с runtime include и `pytest>=8.3,<10`; проверить установку в отдельный .venv, фактическую версию MCP и доступность v2 Client без изменений backend dependencies.

## 2. Connection and discovery CLI

- [x] 2.1 Реализовать entry point через default SDK v2 Client для единственного `https://mcp.deepwiki.com/mcp` по Streamable HTTP без auth; проверить по исходнику отсутствие принудительного handshake/protocol revision, других серверов, tools/call, LLM и импортов backend. Подтверждение реального connection/negotiation выполнить в 5.1.
- [x] 2.2 Реализовать tools/list и маленький цикл по next_cursor до полного каталога; проверить controlled одно- и двухстраничные ответы без hardcoded DeepWiki names/count и без отдельной pagination abstraction.
- [x] 2.3 Вывести endpoint, connection/negotiation success, negotiated protocol_version, optional server identity/version, count и name/description/input schema каждого tool; проверить читаемый Unicode JSON с вложенными полями, отсутствие optional metadata и честный вывод 0 tools.
- [x] 2.4 Добавить ограниченное ожидание async connection/discovery, закрытие SDK context и различимые success/error outcomes; проверить controlled error с ненулевым exit code и без финального success, а сообщение нормального завершения разместить после выхода из context.

## 3. Proportional deterministic checks

- [x] 3.1 Добавить один `tests/test_discovery.py` для собственной логики formatting/catalog aggregation/error outcome согласно Design, используя SDK data models и минимальные локальные fakes только при необходимости; проверить отсутствие network calls, собственного MCP server и protocol/mock framework.
- [x] 3.2 Из каталога Day 16 выполнить `python -m pytest -q` и проверку синтаксиса `python -m py_compile main.py tests/test_discovery.py`; подтвердить успешный результат, отсутствие обращения к backend/базам и что offline результат не выдаётся за live acceptance.

## 4. Documentation and scope review

- [x] 4.1 Добавить краткий русский Day README с сутью, проверяемым поведением, текущим статусом результатов и минимальными standalone setup/run/test командами; проверить, что до live нет утверждения об успешном подключении и нет требования OPENAI_API_KEY/backend/Android.
- [x] 4.2 Добавить в root README одну относительную ссылку `day-16-mcp-discovery/README.md` после Day 15; проверить существование целевого файла, порядок дней и отсутствие дубликатов.
- [x] 4.3 Просмотреть git diff/status и соответствие реализации Specs: изменения ограничены Day 16, ссылкой root README и артефактами этого change; проверить отсутствие секретов, tracked venv/cache, изменений Days 11–15 и исключённых интеграций. Общие backend/Android тесты не запускать без затронутого поведения.

## 5. Separate live acceptance and demonstration

- [x] 5.1 Выполнить отдельный реальный запуск CLI к DeepWiki и проверить все шесть условий: remote connection, successful protocol negotiation, реальный tools/list, непустой каталог, читаемые definitions и clean exit code 0. Зафиксировать команду, фактический вывод и exit code; при failure или пустом каталоге оставить acceptance невыполненным, без подмены данных или сервера.
- [x] 5.2 Обновить раздел «Результаты» Day README по фактическому live: дата, полученный count и ограниченный вывод о connection/negotiation/discovery; проверить отсутствие фиксированных ожиданий names/count, вымышленных результатов и утверждений о выполнении tools или качестве MCP.
- [x] 5.3 Подготовить демонстрацию команды, каталога и exit code для видео Day 16; считать видео готовым только при наличии записи либо явного подтверждения пользователя, не подменяя его успешным terminal run.

Видео готово по явному подтверждению пользователя 2026-09-21: показаны запуск CLI, connection, protocol negotiation/version, реальный tools/list, каталог/definitions и clean exit code 0. Live acceptance не повторялся; сохранённый live-result.md оставлен без изменений как отчёт о предыдущем запуске.
