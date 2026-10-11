## 1. Preserve the existing tool and extract the shared operation

- [x] 1.1 Зафиксировать исходный git status и hashes исторических fixtures/results/planning Days 27–29; проверить отсутствие изменений Weeks 1–5 и согласовать точечный список изменяемых core-файлов с design, не очищая текущий checkout.
- [x] 1.2 Выделить из rag_cli единую возвращающую result/sources/metrics операцию и подключить её обратно к CLI; проверить прежние аргументы, exit codes, rendering, wire prompt/schema и ошибки существующими focused regression tests без inference.
- [x] 1.3 Добавить в общий context packer необязательную недоверенную историю и deterministic retrieval query из текущего вопроса, последнего user-вопроса и filename; проверить прежний payload без истории, лимиты 2000/4096/64 terms, настоящее контекстное уточнение и отказ для evidence только из assistant history.
- [x] 1.4 Добавить обратно совместимые typed error categories и управляемые конечные transport timeouts; проверить status mapping/no retry/proxy/redirect и прежнее CLI-поведение на fake transport.

## 2. Optional HTTP installation and server-owned configuration

- [x] 2.1 Создать Day 30 HTTP-адаптер с отдельными requirements и штатным loopback launcher, одним worker без reload/autostart; проверить установку/импорт в HTTP-окружении и отсутствие FastAPI/Pydantic/Uvicorn в зависимостях core CLI.
- [x] 2.2 Реализовать локальную конфигурацию token labels/secrets, разрешённых file_id, раздельных Workspace/Knowledge и Coder profile/digest; проверить fail-closed при неверной конфигурации, отсутствие секретов в tracked examples и отсутствие автоматического pull/index/inference.
- [x] 2.3 Подключить единую операцию с существующим FTS5 retrieval, top_k 4 и фиксированными 8192/2048 settings; проверить fake upstream payload, отсутствие Day 29 experimental schema и отказ для remote URL/model/digest mismatch.
- [x] 2.4 Проверить CLI-only сценарий в окружении без HTTP-пакетов при выключенном HTTP/Tailscale, используя mocks для model calls; зафиксировать успешность help/knowledge/search/explain smoke и отсутствие новых HTTP-import dependencies.

## 3. Chat API and minimal client

- [x] 3.1 Реализовать POST /v1/chat с file_id/question/history, strict extra-fields rejection и точным правилом двух пар/8 KiB; проверить Unicode и границы размеров, initial/follow-up, запрет system/tool/path/model полей до downstream I/O.
- [x] 3.2 Подключить server allowlist и повторные safe read/freshness checks каждого хода; проверить unknown ID, traversal/absolute/UNC/ADS, links/junctions, overlap roots, stale/corrupt index и отсутствие автоматических writes/fallback.
- [x] 3.3 Сформировать response envelope с request_id, текущими source descriptors, mechanical_validation и semantic_status; проверить done/stop, length, malformed output, invalid IDs/lines/quotes и отсутствие raw upstream/полного corpus в диагностике.
- [x] 3.4 Добавить минимальный интерактивный клиент со stdin-вопросами, in-memory history и tokens вне shell arguments; проверить контекстное question/follow-up/reset/file switch/exit, удаление целых старых пар с уведомлением и отсутствие transcript-файлов; документировать Bearer-вызов со второго устройства без Android/web UI.
- [x] 3.5 Реализовать health/readiness/status с отдельными семантиками и коротким metadata timeout/cache; проверить отсутствие inference/preload/embed, безопасный состав ответа и доступность health/status при двух занятых chat slots.

## 4. Security limits and concurrency

- [x] 4.1 Реализовать Bearer auth с constant-time comparison и отдельные token buckets chat 6/min burst 2 и ready/status 30/min burst 5; проверить missing/invalid token, fake-clock refill, независимость token budgets, 429/Retry-After и отсутствие downstream I/O при отказах.
- [x] 4.2 Ограничить поток HTTP-body 32 KiB и 10 s до полного JSON parsing, запретить compression/non-JSON; проверить Content-Length, chunked/no-length, stalled body, 413/415/504 и bounded buffer.
- [x] 4.3 Обеспечить фиксированные file/question/history/full-body/context/output caps и применение общего packer; проверить граничные значения, context_budget_exceeded, selected/omitted и отсутствие скрытого обрезания истории/исходника.
- [x] 4.4 Добавить fail-fast admission двух chat на один процесс и ограниченное исполнение sync core вне event loop; deterministic barrier tests должны показать два допуска, третий 503/Retry-After, max_active=2, отсутствие смешения результатов и application waiting queue.
- [x] 4.5 Реализовать 120 s absolute deadline, ownership незавершённых операций, disconnect и recovery_required без retry; fake tests должны показать своевременный 504, отсутствие premature slot reuse, блокировку новых calls и восстановление только по допустимому подтверждению.
- [x] 4.6 Настроить фиксированные safe errors и allowlisted metadata logs, no-store, выключенные raw access/debug/docs endpoints; проверить canary markers в invalid request/upstream/internal error, unknown routes и отсутствие tokens/paths/history/code/quotes в логах и ошибках.
- [x] 4.7 Реализовать ограниченный shutdown без управления чужими процессами; проверить прекращение допуска, учёт незавершённой работы, честный unknown cleanup и сохранность CLI/Knowledge/index/models после остановки HTTP.

## 5. Integrated offline verification and documentation

- [x] 5.1 Выполнить offline integration через настоящий loopback HTTP server, fake Ollama и два независимых TCP-клиента; проверить перекрытие запросов, два результата, третий отказ и отзывчивость health без real inference.
- [x] 5.2 Запустить необходимые core/Day 30 regression tests и затронутые Day 29 offline tests без experimental runtime changes; проверить синтаксис Python, структуру файлов, отсутствие новых секретов/кэшей и неизменность исторических hashes.
- [x] 5.3 Создать краткий русский Day README по шаблону проекта с фактическими/pending результатами и добавить относительную ссылку в раздел «Задания» корневого README; проверить существование цели, порядок и отсутствие дубликатов.
- [x] 5.4 Документировать отдельную установку HTTP, localhost start/stop, client history, настройки Ollama без автоприменения, tokens, limits и recovery; проверить команды Windows и явную возможность CLI-only, не запуская старый backend/Android.
- [x] 5.5 Документировать отдельный gate Tailscale Serve, разрешённый route/HTTPS/access policy и выключение только Day 30 route; проверить отсутствие обязательных VPS/public IP/domain/Funnel/Mac задач и явное отличие private internet access от public hosting.

## 6. Windows local live acceptance — only after separate live authorization

- [x] 6.1 После явного разрешения live выполнить read-only preflight версии/digest/local-only, loopback listeners и synthetic Workspace/Knowledge; проверить готовность без warm-up. Если нужен новый index, отдельно объявить и разрешить embedding inference, учесть его вызовы и не менять исторические индексы.
- [x] 6.2 Выполнить первоначальный вопрос и уточнение с клиентской историей на Windows, максимум 2 chat calls; проверить done/stop и mechanical validation каждого, отдельно записать semantic review и не повышать статус Coder/Day 29.
- [x] 6.3 Выполнить локальную конкурентную пару независимых клиентов при штатной очереди Ollama; проверить два принятых перекрывающихся запроса и два отдельных успешных ответа, отделив HTTP concurrency от не измеренного inference parallelism. Первая пара (2 calls) дала один 502/length; FAIL сохранён. Отдельно разрешённая 2026-10-11 дополнительная пара (2 calls, более узкие вопросы, неизменные настройки) дала два 200/done/stop/validation passed, max_active=2 и health PASS; см. live-concurrent-additional-2026-10-11.md. Дальнейшие локальные эксперименты не выполняются.
- [x] 6.4 Зафиксировать safe metrics и отдельные verdicts local scenarios; проверить stop-on-error и отсутствие автоматического retry. Если шаг не завершился, оставить его открытым с причиной и остановить оставшиеся live calls до нового разрешения.

## 7. Private remote demonstration — separate Tailscale approval and live authorization

- [ ] 7.1 Получить отдельное подтверждение установки/настройки Tailscale, подготовить Serve только к HTTP-порту и ограниченный tailnet access; проверить HTTPS/auth и недоступность Ollama/каталогов со второго устройства. HTTPS health и Bearer readiness с Android PASS; remote negative access checks и review tailnet policy не завершены (live-remote-2026-10-11.md), задача остаётся открытой.
- [ ] 7.2 После разрешения remote live выполнить одну пару с двух физических устройств, одно из другой сети через интернет, максимум 2 chat calls; проверить два отдельных завершения и безопасно записать маршрут/тайминги. Remote HTTP concurrency PASS, но два успешных клиентских ответа FAIL/NOT CONFIRMED: Windows 200, Android disconnect и подтверждённый 503 дополнительной HTTP-попытки. Оба внутренних inference завершились, израсходовано 8/8; без повторов и расширения бюджета. См. live-remote-2026-10-11.md. Исходный потолок 6 и отдельное перспективное увеличение до 8 сохранены в evidence/design.
- [x] 7.3 Отключить только созданный для Day 30 Serve route и проверить его недоступность, затем проверить сохранность локального CLI/HTTP по выбранному состоянию; зафиксировать отсутствие Funnel/public exposure и не сбрасывать чужие настройки. Serve {}, HTTPS connection refused, HTTP listener8030=0, phone token отозван; Ollama/CLI/corpus сохранены (live-remote-2026-10-11.md).
- [x] 7.4 Обновить Day README и техническое evidence только фактическими результатами Windows/local/remote/semantic, выполнить OpenSpec strict validation и проверить ссылки/git diff; Mac остаётся отдельным NOT TESTED этапом, видео — отдельной пользовательской демонстрацией, commit/push/archive не выполняются без запроса.
