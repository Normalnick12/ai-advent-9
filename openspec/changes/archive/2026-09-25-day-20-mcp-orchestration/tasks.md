## 1. Изолированный запуск и задача

- [x] 1.1 Добавить Day 20 backend contract/service/route и CLI в `day-20-mcp-orchestration/`, сохранив старые маршруты; проверить локальный API с fake provider и отсутствие обязательной Day 20 config для запуска прошлых Days.
- [x] 1.2 Сформировать два фиксированных MCP descriptors, отдельные allowlists и server-side конфигурацию; recording-client test должен подтвердить один request, оба labels/URLs, auto, отключённые retries, конечные limits и отсутствие save/Context7/секретов в prompt.
- [x] 1.3 Подготовить обычное задание по двум инженерным ролям и формат итоговых branch records без tool names, готовых координат и полного порядка; review actual request fixture должен подтвердить, что backend не подставляет следующий call и не зашивает Room/WorkManager как ответ.

## 2. Простое evidence первой попытки

- [x] 2.1 Добавить уникальный локальный attempt directory без перезаписи, сохранение конфигурации без секретов и один SDK stream с простым event log, native items/results и raw answer; fixture должна подтвердить оба labels, arguments/outputs и сохранность существующего каталога без API idempotency или durable protocol.
- [x] 2.2 При timeout/storage/stream interruption обозначать evidence как неполное без retry/repair и recovery; компактные fixtures неполного log/response должны давать NOT_PROVEN там, где фактов недостаточно, и не инициировать второй provider request. Исчерпывающая матрица storage failures не нужна.

## 3. Узкая независимая проверка flow

- [x] 3.1 Проверить registration/import, calls обоих labels и согласованность явного repository excerpt с lookup coordinates; fixtures должны обнаруживать неверный server, tool error и неподтверждённые координаты, сохранять все дополнительные calls. Использовать фактический provider format, без generic source parsing и reviewer workflow; неизвестная truth/revision показывается как ограничение NOT_PROVEN.
- [x] 3.2 Связать две ветки по фактическим coordinates/lookup_id, сравнить полный lookup result с summary input и независимо пересчитать count/last_three/hash; focused fixtures должны обнаруживать смешение веток и изменение переданных данных, без production summarizer и универсального adversarial JSON validator.
- [x] 3.3 Проверить совместимость runtime order с DAG и раздельно оценить final facts; fixtures должны принимать оба допустимых interleavings, обнаруживать обратный порядок/отсутствующую ветку в полном response, давать NOT_PROVEN при нехватке evidence и сохранять flow PASS с final FAIL при неверном model count. Verifier работает только offline.

## 4. Читаемый результат и offline gate

- [x] 4.1 Сделать `report.md` и CLI главным human-facing результатом: задача, зачем понадобился repository research, выбранная DeepWiki capability, найденные dependencies, смысл перехода к Dependency MCP, обе lookup/summary ветки, инженерный итог и независимые trace подтверждения. Проверить на успешной и неполной fixtures понятность без verifier JSON, видимость всех calls и отдельность исходного model answer от проверенных фактов.
- [x] 4.2 Создать краткий Day README с непроверенным пока live, root README ссылку, backend/scripts инструкции подготовки, запуска и чтения сохранённой попытки; проверить относительные ссылки и наличие объяснимой последовательности для видео без повторного model run.
- [x] 4.3 Выполнить focused Day 20 offline suite и затронутые backend API/MCP regression tests, синтаксис, JSON parsing, `git diff --check` и проверку secrets/local files; сохранить краткие результаты, подтвердить отсутствие внешнего DeepWiki/Google Maven flow в тестах. Android build/UI checks не требуются при отсутствии Android изменений.

## 5. Подготовка отдельного live

- [x] 5.1 Подобрать и зафиксировать конечные output budget/deadline по offline payload sizing для двух полных transfers и research, проверить локальное evidence storage; доставляемый configuration summary должен содержать rationale и ограничения без реального dependency flow и без секретов.
- [x] 5.2 Проверить штатные protocol/tools-list обоих существующих endpoints и готовность backend через `scripts/dev.ps1`, сохранить это отдельно как readiness; не вызывать research/lookup/summary, не менять VPS, не считать discovery доказательством model orchestration. При недоступности endpoint записать конкретный blocker.

## 6. Одна отдельная live-попытка и фактический итог

Этот этап выполняется после реализации/offline/readiness по отдельному явному запросу на live. Создание или review proposal не разрешает implementation; apply не запускает live автоматически. Повтор ради улучшения результата не предусмотрен.

- [x] 6.1 Выполнить одну отправку подготовленного инженерного задания в новом локальном каталоге; проверить сохранение request, доступных native events/items/results и исходного ответа, зафиксировать любой success/failure/incomplete без второго model run или tool repair.
- [x] 6.2 Запустить узкий verifier только на сохранённых данных; получить flow и final verdicts, показать фактические research excerpts и ограничения truth/revision, сохранить исходную попытку неизменной. Проверить, что пробелы обозначены NOT_PROVEN и не восполняются новыми model/MCP calls; отдельный source-review этап не требуется.
- [x] 6.3 Обновить Day README и читаемый результат по фактам единственной попытки, проверить root link и возможность показать flow на видео из сохранённого evidence; не объявлять неподтверждённые источники или незаписанное видео успешными. Commit/push/archive выполнять только отдельным finish workflow.

## Apply checkpoint — 2026-09-25

Выполнены 12/16 tasks. Offline suite: 110 passed; после правки отображения
runtime order дополнительно verifier/report suite: 20 passed. Strict OpenSpec,
syntax/JSON, README links и git diff --check: PASS. Сводки сохранены в
`day-20-mcp-orchestration/evidence/`; synthetic preview не является live.

5.2 частично выполнена: backend /health и маршрут доступны, DeepWiki tools/list
PASS. Фактически опубликовано имя `ask_wiki_question`; allowlist и design
уточнены по discovery. Локальных DAY19_MCP_SERVER_URL / DAY19_MCP_TOKEN нет;
старый launcher получал token через SSH и не использован. Для завершения readiness
нужно предоставить credentials локально и выполнить только discovery.
Задача остаётся открытой, доступность Dependency MCP не заявляется.

6.1–6.3 не выполнялись: модельных Day 20 отправок 0. Live, видео и finish
остаются отдельными явными шагами.

### Повторная проверка локальной конфигурации — 2026-09-25

Task 5.2 остаётся BLOCKED и не отмечена выполненной. URL найден в
`.local/day19-prelive/backend-configuration.json` и подтверждён сохранённым
Day 19 evidence. Authorization в этих records redacted; рабочего token нет
в process/user/machine environment и проверенных root/backend/Day 19 .env.
Локальную конфигурацию backend не меняли и без token не перезапускали.
/health существующего backend повторно PASS. DeepWiki PASS относится к
сохранённому tools/list; новых внешних calls на этом шаге не было.
Нужен существующий DAY19_MCP_TOKEN, предоставленный локально через environment
или backend/.env. SSH и live не выполнялись. Подробности —
`day-20-mcp-orchestration/evidence/readiness-local-config-check-20260925.json`.

### Единственная разрешённая credential read — 2026-09-25

Одна SSH-команда чтения существующего env завершилась nonzero; credential
не получен, повторов не было. SSH stdout/stderr не раскрывались и не сохранены.
Локальный backend восстановлен через scripts/dev.ps1 backend без MCP token;
/health PASS. Dependency protocol/tools-list не выполнялись, task 5.2 BLOCKED,
12/16 tasks. Изменений VPS и model/tool calls нет. Evidence:
`day-20-mcp-orchestration/evidence/readiness-credential-attempt-20260925.json`.

### Readiness 5.2 завершена — 2026-09-25

После восстановления Windows ssh-agent выполнена одна отдельно разрешённая
повторная SSH-команда чтения существующего credential. SSH transport/auth и
credential retrieval PASS. Token перехвачен private pipe и передан только
через process environment локальному backend и discovery helper; его значение
не выводилось и не записывалось в файлы.

Backend перезапущен через scripts/dev.ps1 backend; /health PASS.
Dependency Composition MCP protocol/tools-list PASS; опубликованы
get_google_maven_versions, summarize_dependency_versions, save_dependency_report.
Для Day 20 по-прежнему импортируются только lookup и summary.
DeepWiki PASS переиспользован из сохранённого tools/list.
Evidence: `day-20-mcp-orchestration/evidence/readiness-retry-20260925.json`.

Task 5.2 PASS; закрыто 13/16 tasks. Credential доступен работающему backend
только в его process environment; после остановки процесса он не сохраняется.
VPS не изменён, tools/call и модель не вызывались. Readiness не доказывает
orchestration. Tasks 6.1–6.3 остаются открытыми до отдельного разрешения live.

### Единственная live-попытка и offline review — 2026-09-25

Tasks 6.1 и 6.2 выполнены по отдельному разрешению пользователя.
Attempt `329e8e15-ce73-4c14-9a89-4cf4b1f56e1a`, response
`resp_0e5536fbc312b329016ab67e3c8d3c87d2ba14c7d4d103943f`, completed.
Одна отправка, два одновременно зарегистрированных MCP servers, auto, retries=0.
Сохранены конфигурация, native events/imports/calls/results, response и исходный
model answer в `backend/.local/day20/329e8e15-ce73-4c14-9a89-4cf4b1f56e1a/`.

Порядок: DeepWiki ask_wiki_question ×2 (разные вопросы), Room lookup → summary,
WorkManager lookup → summary. Coordinates: androidx.room:room-runtime (92),
androidx.work:work-runtime-ktx (91). Flow PASS; final publication facts PASS.
Для обеих веток exact provenance FAIL и declared_publication NOT_PROVEN;
source_truth/revision NOT_PROVEN. Причины разобраны исключительно offline в
`review/review-notes.md`; original report/verdict/evidence не изменены.
Нет второго model run, ручных tool repeats, repair или VPS изменений.

Закрыто 15/16 tasks. 6.3 остаётся открытой: окончательные Day README/results,
видео и finish/commit/push/archive не выполнялись до следующего review.

### Finish checkpoint — 2026-09-25

Пользователь подтвердил запись видео и вызвал finish-day. Task 6.3 завершена:
Day README отражает фактические PASS / FAIL / NOT_PROVEN, root link проверен.
Сохранена byte-identical копия request/events/response/model answer и review
в day-20-mcp-orchestration/evidence/live-20260925; локальный operation.json
с machine path не публикуется. Offline verifier на этой копии воспроизвёл
исходный результат. Новый model/MCP run не выполнялся. Закрыто 16/16 tasks.
