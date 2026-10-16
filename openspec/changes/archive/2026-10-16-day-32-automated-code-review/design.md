## Context

Мотивация и scope — в [proposal.md](proposal.md), проверяемое поведение — в [spec](specs/automated-pr-review/spec.md). На 16 октября 2026 года локальный и серверный `main` указывали на `4a6d5e9`; Day 31 архивирован. Read-only GitHub API подтвердил публичный `Normalnick12/ai-advent-9`, default branch `main`, admin-доступ текущей учётной записи, default token permissions `read`, отсутствие Environments и repository secrets. Существующих workflows при исследовании не было. Настройки не изменялись.

Используются backend Python environment и pytest. Локально проверены версии Python 3.14.7, OpenAI SDK 2.54.0, tiktoken 0.14.0; CI начинает с Python 3.14 на GitHub-hosted Ubuntu. Установка на Linux ещё не проверена. Завершить Days 32–35 нужно до вечера 18 октября: реализация Day 32 ограничена одним рабочим сценарием без развития платформы.

## Goals / Non-Goals

**Goals:** один CLI для локальной диагностики и Actions; неизменяемые revisions данных; документальные и кодовые основания; понятный статус ошибок; минимальная автоматизация создания и обновления отчёта.

**Non-Goals:** исполнение PR-кода, рекурсивный обход импортов, универсальный AST/dependency analyzer, новый Android UI, FastAPI endpoint, VPS, MCP, Ollama, framework агента, persistent memory/index/cache, универсальный GitHub SDK, LLM rewrite/reranker/judge, inline comments, автоисправления/approve/merge, merge gate, отдельная система артефактов и расчёта стоимости. Форки и Dependabot в MVP пропускаются.

## Decisions

### 1. Маленький пакет и переиспользование без изменения контрактов

Новые `backend/scripts/day32_review.py` и `backend/app/pr_review/` разделяют только GitHub transport/snapshot, RAG, service/validation и Markdown publication. Точное число файлов определяется реализацией, без общего plugin/runtime API. Используются существующие `httpx`, OpenAI SDK, Pydantic и tiktoken. CLI локально принимает repository/PR number и выводит отчёт без GitHub mutations; публикация доступна только проверенному Actions-режиму с event/run validation. Аргументы, event JSON и trusted config не дают модели выбирать действия.

| Переиспользуется без изменения | Роль |
|---|---|
| `backend/app/document_indexing/corpus.py`: `Source`, `Snapshot`, hashing | Представление выбранных текстов и идентичность |
| `backend/app/document_indexing/chunking.py`, `structure.py` | `chunk_source`: Markdown/Python/Kotlin, до 500 tokens; существующий AST parsing не исполняет Python |
| `backend/app/document_indexing/embedding.py` | `OpenAIEmbedder`, 1536 dimensions, `text-embedding-3-small`, retries=0 |
| `backend/app/first_rag/core.py`: `Index`, `vector_norm`, `search` | Два временных индекса и cosine ranking |
| `backend/app/llm_client.py`, `openai_responses_llm_client.py`, `openai_agent_payload.py` | Конфигурация, Responses transport, usage/errors, `store=False` |
| `backend/app/openai_token_counter.py` | Один preflight count полного input, включая instructions/schema |
| `day-31-developer-assistant/corpus.json` | Состав пяти документов; manifest читается из trusted reviewer revision |

Из Day 31 заимствуется принцип коротких evidence IDs и восстановления точных цитат Python-кодом. `developer_assistant.answer()` и его Markdown-only loader не подключаются: они имеют собственный контракт и MCP-зависимость. Формат findings требует собственного небольшого validator вместо изменения `GroundedResponse`. Исторические SQLite, baseline IDs и threshold 0.50 не используются. Общий `token_pricing.py` не используется.

### 2. Два workflow и граница доверия

`day32-pr-signal.yml`: `pull_request` с `opened`, `synchronize`, `reopened`, base `main`; `permissions: {}`; один фиксированный signal step, без checkout, dependencies, secret или artifacts. Поскольку workflow может быть изменён в PR, его успешный результат является только сигналом для проверки metadata.

`day32-pr-review.yml`: `workflow_run: completed` для signal workflow. Проверяет через REST repository ID, ожидаемый workflow ID/path, исходный event `pull_request`, conclusion `success`, ровно один связанный открытый PR, base `main`, совпадение head repository и SHA, отсутствие Dependabot. Workflow ID сверяется с ID фиксированного signal path в целевом repository. Отсутствующая/неоднозначная PR association означает явную остановку, без угадывания номера по имени ветки или чтения artifacts.

Reviewer workflow и checkout происходят из `main`; checkout фиксируется на `github.sha` самого доверенного `workflow_run`, а не `workflow_run.head_sha`. Записывается `reviewer_sha`. `persist-credentials: false`; зависимости устанавливаются только из этого checkout. Actions закрепляются полными SHA. Никакие artifacts/caches signal workflow не загружаются. PR-файлы остаются текстами в памяти, не записываются в import path или рабочее дерево ревьюера. Git checkout/fetch PR, `pip install` из PR, imports/pytest/Gradle проверяемого кода отсутствуют. Модель не получает tools.

Permissions reviewer job: `contents: read`, `actions: read`, `pull-requests: write`, остальные отсутствуют. Environment — `day32-review`; `OPENAI_API_KEY` задаётся только в env шага OpenAI, GitHub token — только для GitHub API. Значения PR title/body, filename и model output не интерполируются в shell. Сервис обращается только к фиксированным GitHub API/OpenAI endpoints и строит пути сам, не следует ссылкам из документов/ответов; токены не отправляются на произвольные redirect hosts.

Environment разрешает **Selected branches and tags → Branch: main**, без разрешения PR refs/tags и без required reviewers/wait timer, чтобы запуск оставался автоматическим. Ключ не дублируется в repository/organization secrets, доступных PR jobs. Main и пользователи с правом менять доверенную конфигурацию остаются границей доверия.

Альтернативы: один `pull_request` смешивает изменяемый workflow с secrets; `pull_request_target` не выбран из-за привилегированного контекста и новых event policies GitHub. Два небольших workflow сохраняют автоматический PR-trigger и доверенный код. Environment используется для ограничения secret, не требует развёртывания сервиса.

### 3. REST snapshot вместо checkout PR

Последовательность: GET PR metadata → paginated GET PR files → GET PR с diff media type → повторная проверка base/head SHA. Проверяются число файлов, статусы, пути и целостность hunks, соответствие additions/deletions и отсутствие пропущенных частей. GitHub endpoint файлов ограничен 3000 файлами, поэтому лимит Day 32 проверяется до получения большого набора. Пустой/отсутствующий patch нельзя трактовать как отсутствие изменений. Raw diff — источник текста изменений, metadata — независимая проверка полноты. Если данные не согласуются, возвращается `incomplete_diff`, без попытки угадать или синтезировать недостающий diff.

Фиксируются `base_sha`, `head_sha` и `merge_base_sha` из REST compare этих зафиксированных commits: старая сторона PR diff относится к merge base, а не обязательно к текущему base tip. Изменённые/новые `.py` и `.kt` и связанные тесты читаются по head SHA; удалённые исходники — по merge-base SHA; действующая документация — по base SHA. Новая документация PR видна как diff, но не становится доверенными инструкциями. Git tree/blob metadata проверяется до чтения: разрешены обычные файлы, symlinks/submodules не разыменовываются. Достаточен узкий REST helper с timeout и лимитами response bytes; общего SDK не создаём.

Разрешены ограниченные UTF-8 текстовые PR. Бинарные, секретные/локальные/generated paths и неподдерживаемые статусы приводят к `unsupported_scope` для всего PR. `.env*`, ключи/сертификаты, `.git`, virtualenv/cache/build/evidence paths исключаются до OpenAI. Нет скрытого частичного ревью. Содержимое подозрительного секрета не выводится; фильтр не обещает обнаружить любой секрет внутри произвольного файла.

### 4. RAG по пяти документам и непосредственным тестам

Документы: `README.md`, `docs/project-structure.md`, `backend/README.md`, `android-app/README.md`, `scripts/README.md` по существующему trusted manifest Day 31. Дополнительные specs, README других дней и обход ссылок не добавляются.

Код: изменённые `.py`/`.kt` и существующие очевидные тесты. Для Python — bounded naming convention `backend/tests/test_<module>.py` и маленькая явная таблица для существующих RAG-пакетов, например `first_rag` → `test_first_rag.py`, `developer_assistant/index.py` → `test_day31_index.py`, `service.py` → `test_day31_help.py`. Выбирается наиболее прямой тест конкретного модуля: offline-sizing показал 143 chunks demo corpus вместо 162 при одновременном добавлении обоих Day 31 tests; лимит 160 не меняется. Для Kotlin — совпадающий package/basename `*Test.kt` в `src/test`/`src/androidTest`. Отсутствующий convention-кандидат пропускается с записью в coverage; недоступный выбранный источник — ошибка. Не более двух связанных тестов на изменённый файл, после дедупликации. Нет imports traversal, поиска callers или универсальной карты проекта.

Два индекса собираются в памяти из общих chunking/embedding функций; отбор запросов детерминированный: path и ограниченный фрагмент hunks, до 512 tokens на изменённый исходник. Один batch query embeddings, corpus embeddings batches до 32. Каждый запрос ищет в обоих индексах; результаты объединяются по лучшему cosine score с устойчивым tie-break, до 6 documentation и 6 code chunks суммарно, без порога старых экспериментов. Если пригодных code chunks нет, `insufficient_context` до generation. Наличие retrieved chunk не считается доказательством его смысловой релевантности.

Обёртка Day 32 хранит для каждого evidence path, revision, start/end line, text hash, kind и короткий уникальный ID. Общие chunk IDs не меняются; revision добавляется в идентичность обёртки, чтобы не смешать одинаковые пути разных snapshots. Модели передаются отдельные блоки diff, documentation, code. Scores/vectors не нужны в prompt; Summary показывает выбранные paths/lines/revisions и число источников без полного prompt.

### 5. Одна генерация и Python validation

Отдельный `AgentConfig`: `gpt-5.6`, reasoning `none`, `max_output_tokens=4000`, `truncation=disabled`, `store=False`, strict JSON schema. Используется существующий adapter с timeout 75 seconds и retries=0. Нет автоматических повторов после timeout, repair, judge или LLM query rewrite. Если 75 seconds окажутся недостаточны, это диагностируемый blocker; общий transport старых дней молча не изменяется.

Модель возвращает `status` (`reviewed`/`insufficient_context`), короткий summary, findings с category (`bug`/`architecture`/`recommendation`), severity, объяснением, рекомендацией, `change_id` и `context_ids`, а также limitations. Пустые категории и пустые findings разрешены. Каждому `change_id` Python заранее сопоставляет конкретный изменённый диапазон и сторону diff; чистые context lines не являются допустимым якорем finding. Для удалений ссылка ведёт на merge-base revision, для добавлений — на head. Context IDs могут быть пустыми для самодостаточного основания в diff; проектное правило должно ссылаться на предоставленный документ/код.

Validator проверяет schema, enum/size constraints, IDs, принадлежность изменению и уникальность references. Python сам восстанавливает цитаты и GitHub blob links с URL-encoded paths; модель не задаёт URLs или команды. Markdown экранируется, произвольные HTML/images и активные mentions из данных не публикуются. Невалидный результат целиком получает `validation_error`, не исправляется другой генерацией. Валидные ссылки не доказывают правильность вывода: ручная оценка обязательна для live-приёмки.

### 6. Конечные лимиты и явные исходы

| Ограничение MVP | Значение |
|---|---:|
| Изменённых файлов, включая документацию | 10 |
| Raw diff | 128 KiB и не более 1000 добавленных/удалённых строк |
| Diff text | 12 000 tokens существующего tokenizer |
| Один source / весь выбранный corpus | 256 KiB / 2 MiB |
| Файлов corpus после дедупликации | 25 |
| Corpus chunks до embeddings | 160, каждый до 500 tokens |
| Query embeddings | До 10 запросов по 512 tokens, один batch |
| Generation context | До 6 documentation + 6 code chunks |
| Полный generation input | 24 000 tokens по существующему provider counter |
| Output / findings | 4000 tokens / до 10 findings |
| OpenAI calls | До 5 corpus embedding batches + 1 query batch + 1 count + 1 generation |
| Workflow / HTTP timeout | 10 минут / конечные transport timeouts |

Preflight corpus/diff limits проверяются до embeddings, полный input — до generation. При превышении любой границы возвращается `too_large`, без скрытого обрезания diff или дополнительной генерации. Отбор top-k RAG — штатное ограничение контекста, которое показывается в coverage. Exact count error останавливает generation. Все SDK retries отключены; стоимость не рассчитывается, сохраняются доступные token usage/call counts, неизвестные значения не заменяются нулём.

Технические статусы: `configuration_error`, `github_error`, `incomplete_diff`, `provider_error`, `validation_error`, `publication_error`; содержательные/политические: `reviewed`, `insufficient_context`, `too_large`, `unsupported_scope`, `skipped`, `stale`/`superseded`. Exit 0 — завершённый review или явно объяснённый skip/limit; технические ошибки — ненулевой exit. Summary всегда различает эти состояния и не называет skip успешным анализом.

### 7. Комментарий, Summary и защита от запоздавшей публикации

Один comment со стабильным marker Day 32, PR identity, head/base SHA, reviewer SHA и source run identity. Поиск comment пагинируется и проверяет bot author вместе с marker; чужой comment не изменяется. При нескольких собственных совпадениях — publication error вместо удаления чужих данных. Публикуется Markdown по категориям, evidence links, coverage/limitations и ссылки на Actions run. Summary содержит краткий статус, SHA, findings counts, retrieval sources и usage. Не создаётся upload-artifact pipeline или БД; локальный stdout можно сохранить обычным перенаправлением.

Все CI-публикации одного PR используют одну concurrency group, вычисленную из PR number в server-provided workflow_run association, с `cancel-in-progress: false`. Если association отсутствует, используется изолированный run key и запуск останавливается без публикации. Перед любой записью повторно проверяются PR state, repository, base/head SHA и metadata существующего bot comment. Порядок очереди не предполагается FIFO: старый source run не может заменить опубликованный более новый source run; устаревший head немедленно даёт `stale`. Повтор уже успешно опубликованной пары head/base с тем же reviewer/config может завершиться без OpenAI.

Для ошибки текущего подтверждённого PR можно обновить тот же comment явным статусом ошибки; stale/unresolved run пишет только Summary. Если комментарий недоступен, Summary и exit code сообщают `publication_error`, без повторной генерации. GitHub не предоставляет атомарную операцию «проверить PR SHA и изменить comment»: head может измениться непосредственно после проверки. Поэтому comment всегда явно привязан к SHA, после записи выполняется короткая read-only сверка; при гонке Summary отмечает устаревание. Сериализация не позволяет старому завершению затереть уже опубликованный новый отчёт. Локальный CLI не является вторым writer.

```text
PR event --> signal (no key) --> workflow_run (trusted main)
                                   |
                    validate run + PR + pinned SHAs
                                   |
                    REST diff + docs + code/tests
                                   |
                    bounded chunks --> embeddings
                                   |
                   docs search + code search + diff
                                   |
                  input count --> one Responses call
                                   |
                   validate IDs + changed-line anchors
                                   |
                  recheck PR --> bot comment + Summary
```

### 8. Компактная проверка и воспроизводимое видео

Offline: fixtures реального формата GitHub для diff/rename/delete/пагинации/неполных данных и лимитов; fake embeddings/LLM для двух групп retrieval, revisions, invalid IDs/lines, incomplete и provider errors; fake GitHub для event gates, stale/concurrent publication и обновления только своего comment. Проверка workflow structure включает main checkout, Environment, permissions, concurrency и отсутствие PR execution/artifact restore. Live-model prompt injection не является отдельным обязательным экспериментом; offline проверяются границы данных и отсутствие tool execution.

Целевая регрессия: `test_document_indexing.py`, `test_first_rag.py`, `test_agent_adapter.py`, `test_day31_index.py`, `test_day31_help.py`; новые `test_day32_*.py`. `test_grounded_rag.py` добавляется, только если его helper фактически импортируется. `pip check`, проверка синтаксиса Python и структуры YAML выполняются один раз на актуальном коде. Тесты trusted implementation выполняются без OpenAI key; тесты PR не запускаются reviewer job. Android/Gradle и полный backend suite не нужны без выявленной связанной регрессии.

Live после bootstrap: отдельная ветка `codex/day32-review-demo`, PR в `main`, ровно два заранее известных дефекта: (1) сортировка cosine по возрастанию в `backend/app/first_rag/core.py`; (2) отключение freshness comparison в `backend/app/developer_assistant/index.py`. Существующие tests и base `backend/README.md` дают проверяемые основания; список ожидаемых дефектов не подмешивается в prompt. Reviewer продолжает импортировать корректные функции из trusted `main`, даже когда PR изменяет те же файлы.

Первый автоматический run должен найти оба дефекта, указать корректные changed anchors и содержательно подходящие основания; вручную проверяется, что RAG действительно передал документацию и код, а ссылки соответствуют revisions. Исправляющий commit восстанавливает оба поведения и сохраняет небольшое безвредное изменение (например, нейтральный комментарий), чтобы PR diff оставался непустым. Второй автоматический run должен проверить новый SHA, обновить тот же comment ID и больше не утверждать наличие исправленных дефектов. Иные замечания оцениваются отдельно; требование пустого findings array не вводится.

Видеосценарий 3–4 минуты: небольшой diff → создание PR и Actions → findings/источники → исправляющий commit → новый SHA и обновлённый comment. Ожидание runner можно вырезать; сохранённый вывод обозначать как replay. В design/tasks или Day README после приёмки фиксируются PR URL, два run URL, SHA, comment ID и краткий ручной итог, без новой подсистемы evidence. Видео записывает пользователь; наличие файла не выдумывается. Неуспех выявления известного дефекта фиксируется честно и требует конкретной диагностики, без бесконечных повторов до удобного ответа.

## Risks / Trade-offs

- Ограниченный corpus не видит удалённые зависимости → coverage и отказ при нехватке; не расширять scope ради универсального поиска.
- Недоверенный текст может влиять на вывод модели → отдельные инструкции, отсутствие tools, проверяемые IDs, ручная оценка; semantic correctness не гарантируется.
- REST snapshot/публикация не атомарны → pinned SHAs, проверки до/после, per-PR serialization и явный SHA отчёта.
- Source run association может отсутствовать → fail closed; подтвердить на первом настоящем собственном PR, не строить speculative fallback.
- Linux installation, GitHub permissions, model timeout остаются непроверенными → early focused checks и два реальных запуска; ошибки не маскируются.
- Документация корпусов Day 31 содержит разные Days → не переносить локальные правила одного Day на весь репозиторий без основания.
- Нет cache и cost subsystem → повторные embeddings ограничены по объёму; бюджет не заменяет проверку качества.
- До вечера воскресенья остаются другие Days → ориентир 6–10 часов плюс резерв CI/live; при блокере сначала устранять конкретную причину, не добавлять инфраструктуру.

## Migration Plan

1. После review planning и отдельного apply реализовать CLI/package/workflows/tests/docs. Создать Day README из трёх разделов, добавить относительную ссылку в «Задания» корневого README; технические команды — в backend/scripts README. До live результаты обозначать как непроверенные.
2. Пройти offline и целевую регрессию. Затем отдельно получить разрешение на bootstrap commit/push доверенной реализации в `main` и на demo PR/исправляющий push: текущий planning-запрос этого не разрешает. Bootstrap не означает финализацию Day 32; live/video checkboxes остаются открытыми.
3. Настроить GitHub Environment/secret, проверить ограничения и выполнить два автоматических live-run. Demo defect commits никогда не сливать. После видео закрыть demo PR без merge; финальные docs/архив/commit/push — только по отдельному запросу завершения дня.
4. Rollback: отключить только Day 32 reviewer workflow и удалить/отозвать его Environment secret при необходимости; старые Days не имеют зависимости от этой автоматизации. Отключение/удаление настроек — отдельное разрешённое действие, не часть planning.

### Ручные действия пользователя в GitHub UI

После готовности реализации, **не сейчас**:

1. Settings → Environments → New environment: `day32-review`.
2. Deployment branches and tags → Selected branches and tags → добавить только **Branch: main**, без tags и `refs/pull/*/merge`. Не выбирать Protected branches only: без branch protections это может разрешить все ветки. Не включать required reviewers/wait timer; при доступности отключить bypass protection rules.
3. Environment secrets → Add secret → `OPENAI_API_KEY`; значение вводить непосредственно в GitHub, не в чат. Не создавать дубликат repository secret.
4. Если первый workflow показывает permission/policy error, проверить Settings → Actions → General. Достаточно разрешить используемые официальные Actions; глобальное write-all и разрешение approve PR не нужны. Не ослаблять Environment policy ради прохождения запуска.

Создание/изменение demo PR через `gh`, bootstrap и итоговые Git-операции агент может выполнить после явного разрешения; обязательного ручного merge в UI нет. Пользователь вручную оценивает findings и записывает видео.

Фактическая доступность Environment API подтверждена чтением пустого списка для публичного репозитория; configured branch policy, получение key только из main, установка на runner и публикация comment будут проверены после настройки. Это не отмечено как уже успешно работающая автоматизация.

Официальные основания: [workflow_run и PR events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [Environment setup](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [Environment branch restrictions](https://docs.github.com/en/enterprise-cloud@latest/actions/reference/workflows-and-actions/deployments-and-environments), [PR REST API](https://docs.github.com/en/rest/pulls/pulls), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs). Документация проверена при исследовании 16 октября 2026 года; никаких GitHub settings в этом change пока не изменено.
