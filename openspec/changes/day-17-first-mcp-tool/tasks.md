## 1. Standalone MCP server

- [x] 1.1 Создать `day-17-android-dependency-mcp` с отдельными runtime/dev dependencies, `mcp==2.2.0`, ASGI entrypoint и README; проверить установку в отдельное environment и импорт приложения без OpenAI key, не добавляя environment/cache в Git.
- [x] 1.2 Зарегистрировать один `get_google_maven_versions` через `MCPServer` / `@mcp.tool()` с typed signature, descriptions, Pydantic input/result и read-only annotation; проверить официальным `Client(server)`, что discovery возвращает ровно нужный tool и schema обязательных параметров.
- [x] 1.3 Реализовать строгую validation координат и построение fixed-origin group-index URL; проверить таблицей валидных/невалидных inputs все ограничения specs, точный URL и ноль HTTP calls для каждого invalid input.
- [x] 1.4 Реализовать один ограниченный async Google Maven fetch и XML parsing без retries/redirects/fallback; mock HTTP tests должны подтверждать source order, `found`, `group_not_found`, `artifact_not_found`, `no_versions`, 404-only mapping и отсутствие master-index/Maven Central requests.
- [x] 1.5 Добавить tool execution error mapping для timeout/network/HTTP/XML/oversized response, lookup id и структурированный upstream log; проверить ошибки и корреляцию normal result/log, отсутствие ложного `versions=[]` при failure и отсутствие upstream log при validation failure.
- [x] 1.6 Собрать SDK Streamable HTTP ASGI app с stateless semantics, Uvicorn и явным allowed-host configuration; проверить локальный startup, разрешённый/посторонний Host и in-process structured result/SDK error semantics без собственного protocol harness.

## 2. Изолированная backend operation

- [x] 2.1 Добавить Day 17 request/operation DTO, route `/api/v1/mcp-tool-lab/run`, service/provider lifecycle и `DAY17_MCP_SERVER_URL`; route tests должны подтверждать configuration error без generation и работоспособность прежних routes без Day 17 URL, при неизменном общем `LlmClient`.
- [x] 2.2 Реализовать один native Responses request с forced/auto choice, серверным URL, allowlist единственного tool, `require_approval="never"`, `store=false`, `max_retries=0` и отдельным deadline; SDK mock tests должны проверять payload обоих режимов, один вызов и отсутствие bridge/repair после ошибок.
- [x] 2.3 Сформировать атомарный typed result со снимком попытки, final text/response id, всеми реальными `mcp_list_tools` и `mcp_call`; tests должны подтверждать порядок, imported tools из discovery, raw arguments/output/error, optional status, сохранение evidence при incomplete/refusal и отсутствие смешения двух concurrent operations.
- [x] 2.4 Добавить явный decoder result/error envelope, validation parsed evidence и per-call/operation outcomes из design; fixtures должны покрывать normal/negative/tool/MCP errors, unknown output, координатный mismatch, несколько calls, no-call forced/auto, unexpected approval и provider timeout с invocation unknown без fabricated evidence.

## 3. Android Day 17 lab

- [x] 3.1 Добавить Retrofit DTO/repository и DI для отдельного Day 17 endpoint; mapping tests должны сохранять все calls, null/optional fields и distinctions outcome/error без новых ключей или retry policy на Android.
- [x] 3.2 Добавить ViewModel с default forced prompt, mode, submitted snapshot, loading и одной текущей попыткой; JVM tests должны проверять explicit send, duplicate-send guard, completed/not_called/error/incomplete, success→failure без старого evidence и редактирование draft без изменения receipt.
- [x] 3.3 Добавить экран с двумя режимами, отправкой, final response, кратким outcome и Inspector всех calls/ids/arguments/results; целевые Compose UI tests должны подтверждать раскрытие details, различение provider status/outcome и отсутствие фиктивных fields/giant raw JSON на основном экране.
- [x] 3.4 Добавить Day 17 card после Day 15 и независимый destination/ViewModel; navigation/lifecycle tests должны подтверждать root entry, Back, rotation/reopen без replay, отсутствие initial request и независимость Day 15 Playground. Проверить отсутствие auto send в process-restoration path.

## 4. Offline integration checks

- [x] 4.1 Запустить standalone server pytest, включая официальный in-process `Client(server)` integration, без live upstream/OpenAI; зафиксировать команды и результаты, устранить только обнаруженные ошибки.
- [x] 4.2 Запустить Day 17 backend tests и затронутые startup/router regressions; проверить, что MCP items не проходят через текстовую нормализацию общего `LlmClient`, секреты не логируются и все offline tests обходятся без remote calls.
- [x] 4.3 Выполнить целевые Android JVM/UI проверки и затронутые root-navigation regressions через PowerShell 7 `scripts/dev.ps1` (`unit`, `build`, `ui -Test` по существующей инструкции); проверить compile и no-replay, переиспользуя работающий эмулятор и уже успешные проверки актуального кода.

## 5. Pre-live review и публикация deployable revision

- [x] 5.1 Подготовить Day README с фактическими offline results и явным статусом «live/video ещё не выполнены», component setup docs и относительную ссылку дня в корневом README; проверить порядок, отсутствие дубликатов и существование target до первого commit.
- [x] 5.2 После успешного завершения всех offline checks выполнить scoped diff review Day 17 code/tests/docs/planning, проверить отсутствие секретов/local files и изменений общих Days 6–15 contracts; выполнить `git diff --check` и `openspec validate day-17-first-mcp-tool --type change --strict --no-interactive`, зафиксировать успешные результаты для публикуемой revision.
- [ ] 5.3 Создать отдельный pre-live commit только с deployable Day 17 changes и выполнить обычный push в текущую upstream-ветку; перед commit проверить explicit staged paths, полный staged diff, секреты и `git diff --cached --check`, после push — commit SHA, ветку, результат push и `git status`. Не использовать force/amend; не архивировать change и не отмечать live/video tasks выполненными. Этот checkpoint нужен для Render, а не для завершения дня.

## 6. Render deployment и readiness

- [ ] 6.1 Развернуть только standalone MCP server как Git-backed Render Web Service из опубликованной pre-live revision; проверить root directory, requirements/start command, PORT, allowed host, HTTPS `/mcp` без redirect и отсутствие OpenAI key. Сверить полный SHA фактически запущенного deployment с опубликованной revision; сохранить `deployed_commit_sha`, deployment reference и URL для live evidence. Не добавлять registry/tunnel/другой deployment mechanism.
- [ ] 6.2 Отдельно проверить/при необходимости пробудить remote endpoint официальным MCP Client; сохранить фактический `tools/list` с единственным tool, description/schema и результат readiness для подтверждённого deployment, не считая это model experiment или retry generation.
- [ ] 6.3 Настроить URL на существующем backend, проверить backend readiness и доступность с Android emulator; подтвердить неизменность previous Days timeouts и что следующий live стартует только по явной отправке из Day 17.

## 7. Forced live и optional auto

- [ ] 7.1 Выполнить одну forced попытку с default prompt для `androidx.core:core-ktx`; проверить Android dispatch, response id, все calls, нужный name и actual model-generated arguments, parsed result против raw output и Render upstream log по lookup id. Сохранить вместе с evidence полный `deployed_commit_sha`, deployment reference/endpoint, время и фактический verdict, включая failure; не повторять generation ради красивого результата.
- [ ] 7.2 Проверить final response этой попытки по returned versions: количество и три последних элемента source order; подтвердить отсутствие retry/regeneration/repair и успешный forced acceptance. При неполной цепочке оставить задачу незавершённой и записать failure; после реального исправления выполнить затронутые checks/review, при изменении server code опубликовать новую revision и redeploy, а новый прогон считать отдельной попыткой со своим deployed SHA, сохранив прежнюю evidence.
- [ ] 7.3 Зафиксировать статус дополнительного auto experiment: выполнить отдельную явную попытку с запросом актуальных данных или отметить «не проводился»; если выполнен, сохранить реальный call/`not_called`, deployed SHA и evidence как model-selection observation без повторов и без подмены forced acceptance.

## 8. Видео и передача на finish-day

- [ ] 8.1 После forced live и фиксации статуса optional auto получить подтверждение пользователя, что видео записано; закрывать задачу только по этому подтверждению. Проверить, что записи live evidence содержат deployed SHA, response/call/lookup ids и verdict, а deployment/pre-live commit не использованы как доказательство записи видео.

После выполнения обязательных задач пользователь отдельно запускает `$finish-day Day 17`. Этот workflow актуализирует live evidence, Day/component docs и task statuses по фактам, проверяет root README, scoped diff и секреты, переиспользует актуальные checks или запускает необходимые, выполняет strict validation, затем штатное архивирование/spec sync. Последующие scoped changes (включая evidence/docs/archive) входят в финальный commit/push; пустой commit не создаётся. Архивирование и final commit не являются предварительными checkbox-задачами этого change. Pre-live SHA в evidence сохраняется и не заменяется SHA финального commit.
