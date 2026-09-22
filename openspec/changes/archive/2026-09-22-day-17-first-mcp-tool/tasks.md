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
- [x] 5.3 Создать отдельный pre-live commit только с deployable Day 17 changes и выполнить обычный push в текущую upstream-ветку; перед commit проверить explicit staged paths, полный staged diff, секреты и `git diff --cached --check`, после push — commit SHA, ветку, результат push и `git status`. Не использовать force/amend; не архивировать change и не отмечать live/video tasks выполненными. Этот checkpoint нужен для Render, а не для завершения дня.

## 6. Render deployment и readiness

- [x] 6.1 Развернуть только standalone MCP server как Git-backed Render Web Service из опубликованной pre-live revision; проверить root directory, requirements/start command, PORT, allowed host, HTTPS `/mcp` без redirect и отсутствие OpenAI key. Сверить полный SHA фактически запущенного deployment с опубликованной revision; сохранить `deployed_commit_sha`, deployment reference и URL для live evidence. Не добавлять registry/tunnel/другой deployment mechanism.
- [x] 6.2 Отдельно проверить/при необходимости пробудить remote endpoint официальным MCP Client; сохранить фактический `tools/list` с единственным tool, description/schema и результат readiness для подтверждённого deployment, не считая это model experiment или retry generation.
- [x] 6.3 Настроить URL на существующем backend, проверить backend readiness и доступность с Android emulator; подтвердить неизменность previous Days timeouts и что следующий live стартует только по явной отправке из Day 17.

## 7. Forced live и optional auto

- [x] 7.1 Выполнить одну forced попытку с default prompt для `androidx.core:core-ktx`; проверить Android dispatch, response id, все calls, нужный name и actual model-generated arguments, parsed result против raw output и Render upstream log по lookup id. Сохранить вместе с evidence полный `deployed_commit_sha`, deployment reference/endpoint, время и фактический verdict, включая failure; не повторять generation ради красивого результата.
- [x] 7.2 Проверить final response единственной forced попытки по returned versions: количество и три последних элемента source order. При полной подтверждённой MCP evidence-цепочке зафиксировать отдельно MCP mechanism, factual accuracy и фактический pass/fail verdict, включая ошибку модели; подтвердить отсутствие retry/regeneration/repair. Задача завершена после этой проверки и сохранения evidence, но failed forced acceptance не переименовывается в passed. При неполной MCP-цепочке задача остаётся незавершённой; дополнительная generation не выполняется без отдельного разрешения.
- [x] 7.3 Зафиксировать статус дополнительного auto experiment: выполнить отдельную явную попытку с запросом актуальных данных или отметить «не проводился»; если выполнен, сохранить реальный call/`not_called`, deployed SHA и evidence как model-selection observation без повторов и без подмены forced acceptance.

## 8. Видео и передача на finish-day

- [x] 8.1 После forced live и фиксации статуса optional auto получить подтверждение пользователя, что видео записано; закрывать задачу только по этому подтверждению. Проверить, что записи live evidence содержат deployed SHA, response/call/lookup ids и verdict, а deployment/pre-live commit не использованы как доказательство записи видео.

После выполнения обязательных задач пользователь отдельно запускает `$finish-day Day 17`. Этот workflow актуализирует live evidence, Day/component docs и task statuses по фактам, проверяет root README, scoped diff и секреты, переиспользует актуальные checks или запускает необходимые, выполняет strict validation, затем штатное архивирование/spec sync. Последующие scoped changes (включая evidence/docs/archive) входят в финальный commit/push; пустой commit не создаётся. Архивирование и final commit не являются предварительными checkbox-задачами этого change. Pre-live SHA в evidence сохраняется и не заменяется SHA финального commit.

## Execution evidence — pre-live checkpoint

- Standalone server: `.venv/Scripts/python.exe -m pytest -q` из Day 17 — 57 passed (официальный in-process MCP Client и ASGI tests, без live upstream).
- Backend: `.venv/Scripts/python.exe -m pytest tests/test_mcp_lab.py tests/test_agent_adapter.py -q` — 51 passed; SDK mocked, live Responses не выполнялся.
- Android: `./scripts/dev.ps1 unit -Test '*McpLab*'` — 7 passed; `ui -Test 'com.example.responsecontrollab.McpLabUiTest'` — 2 passed; `ui -Test 'com.example.responsecontrollab.RootNavigationUiTest'` — 8 passed, emulator API 34. Debug APK собран в ходе UI checks.
- Scoped/staged diff и credential-pattern review: 33 файла, секреты/local artifacts не обнаружены; `git diff --check` и strict OpenSpec validation успешны.
- Pre-live commit: `ad1dae7b615072de7fa271a6e94e065373a747cb` — `Prepare Day 17 MCP tool for live deployment`; обычный push `main -> origin/main` успешен.
- Render deployment подтверждён пользователем: `deployed_commit_sha=ad1dae7b615072de7fa271a6e94e065373a747cb`, endpoint/deployment reference — `https://android-dependency-mcp.onrender.com/mcp`. SHA совпадает с опубликованным pre-live commit; источник сведений о запущенной revision — подтверждение пользователя, не чтение Render control plane.
- На момент pre-live checkpoint forced live, optional auto и видео ещё не выполнялись. Результат последующей единственной forced попытки приведён ниже; единственная попытка и её failure сохраняются независимо от последующего уточнения критерия завершения.

## Execution evidence — remote readiness/discovery

- 2026-09-22, 14:13:39–14:13:40 UTC: официальный `mcp.Client(endpoint)` из standalone environment (`mcp==2.2.0`) успешно выполнил negotiation и реальный `tools/list`. Полный каталог, description, input/output schema, annotations, timestamps, HTTP response log и deployed SHA сохранены в [discovery-evidence.json](discovery-evidence.json).
- `/health`: HTTP 200, `{"status":"ok"}`. Оба MCP POST на точный HTTPS `/mcp`: HTTP 200; redirect в HTTP response log отсутствует. Server: `Android Dependency MCP`, version `0.1.0`; negotiated protocol `2026-07-28`.
- Каталог содержит ровно `get_google_maven_versions`; обязательные строковые `group_id` и `artifact_id` имеют descriptions, patterns и длину 1–256. Output schema содержит семь обязательных полей; `readOnlyHint=true`. Verdict: `passed`.
- Ни `tools/call`, ни Responses API request не выполнялись. Discovery не проверяет Google Maven access и не является forced acceptance.
- Task 6.1 завершён: пользователь подтвердил Render configuration — `PYTHON_VERSION=3.14.7`, Auto-Deploy disabled, остальные deployment settings соответствуют согласованным. Это включает Root Directory `day-17-android-dependency-mcp`, build `pip install -r requirements.txt`, start `python -m uvicorn server:app --host 0.0.0.0 --port $PORT`, allowed hostname через `RENDER_EXTERNAL_HOSTNAME` либо `MCP_PUBLIC_HOST` и отсутствие `OPENAI_API_KEY` на MCP service. Источник проверки settings — явное подтверждение пользователя; Render control plane не читался.
- Подтверждённый deployed URL: `https://android-dependency-mcp.onrender.com`; MCP URL: `https://android-dependency-mcp.onrender.com/mcp`; deployed SHA: `ad1dae7b615072de7fa271a6e94e065373a747cb`. Уже успешное readiness/discovery относится к этой revision; повторный remote probe не выполнялся. На момент подтверждения deployment forced live ещё не запускался; последующая отдельно разрешённая попытка описана ниже.
- После сохранения discovery: JSON/revision checks, scoped diff/credential-pattern review, `git diff --check` и strict OpenSpec validation успешны. Runtime code не менялся; offline tests повторно не запускались.

## Execution evidence — forced-01

- Task 6.3 выполнен: backend запущен через `scripts/dev.ps1 backend` с подтверждённым MCP URL; `status` и HTTP `/health` из `emulator-5554` подтвердили readiness. Установлен ранее проверенный APK. Production source/таймауты прежних Days не менялись; Day 17 сохраняет `max_retries=0`, deadline 75 s.
- По явному запросу пользователя после отдельного Render readiness выполнен ровно один tap Android Send с неизменённым default prompt и forced mode. Наблюдаются одна backend operation, один Responses create и один returned MCP call; пробных generation/retry/regeneration/repair не было.
- Task 7.1 выполнен: полный evidence, actual arguments `androidx.core:core-ktx`, raw/parsed result, Render log по lookup id и фактический failure verdict сохранены в [live-result.md](live-result.md) и [manifest](evidence/forced-01/manifest.json). Deployed SHA — `ad1dae7b615072de7fa271a6e94e065373a747cb`.
- Task 7.2 **проверен, semantic acceptance failed**: tool result и Render log содержат 129 версий, final response утверждает 133. Три последних элемента верны: `1.19.0-alpha02`, `1.19.0-rc01`, `1.19.0`. Verdict — `failed_final_response_count_mismatch`; provider/operation `completed` не означает успешный factual acceptance. По указанию пользователя результат не исправлялся и не перегенерировался.
- Task 7.3: optional auto **not performed / не проводился**; пользователь подтвердил, что дополнительный эксперимент не проводится. Task 8.1 завершён по явному подтверждению пользователя: видео Day 17 записано. Дополнительных generation нет.

## Finish-day — 2026-09-22

- Пользователь подтвердил видео, запретил дополнительные generation и явно сохранил фактический failure единственной forced попытки. После обсуждения пользователь поручил закрыть задачу; критерий 7.2 уточнён как завершённая проверка с сохранением фактического verdict при подтверждённом MCP mechanism. Итог — 27/27; успешный forced acceptance не заявляется.
- OpenSpec: `day-17-first-mcp-tool`, все planning artifacts done; 27/27 tasks. Согласованное уточнение отражено в proposal/design/spec/tasks. После strict validation выполняются штатные spec sync и archive; фактический failed verdict остаётся в evidence.
- Reused: standalone `python -m pytest -q` — 57 passed; backend `python -m pytest tests/test_mcp_lab.py tests/test_agent_adapter.py -q` — 51 passed; `scripts/dev.ps1 unit -Test '*McpLab*'` — 7 passed; `ui -Test 'com.example.responsecontrollab.McpLabUiTest'` — 2 passed; `ui -Test 'com.example.responsecontrollab.RootNavigationUiTest'` — 8 passed, APK собран. Код и runtime dependencies не менялись после этих проверок.
- Reused: успешные readiness/discovery и полная MCP evidence-цепочка forced-01; семантический verdict **failed_final_response_count_mismatch**, 129 фактических версий против 133 в final response. Новых remote probes/generation в finish-day нет.
- Корневая ссылка `day-17-android-dependency-mcp/README.md` уже добавлена pre-live commit, уникальна, находится после Day 16 и ведёт на существующий файл; повторная правка index не нужна.
- Байты captured evidence защищены локальным `.gitattributes` от Git line-ending conversion, чтобы SHA-256 manifest оставался проверяемым после checkout. Пассивный observer в evidence — сохранённый audit source, не production hook; `.local`, environments, caches и build outputs в commit не включаются.
- Run: strict change validation passed; после sync strict main-spec validation — 34 passed, 0 failed; все четыре delta сверены с main specs. Evidence hashes/syntax/secret-pattern checks, root README link и `git diff --check` passed. Дополнительные runtime tests/generation не требуются: код не менялся.
