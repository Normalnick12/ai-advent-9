## 1. Corpus and isolated setup

- [x] 1.1 Создать `day-31-developer-assistant/README.md` по шаблону AGENTS.md с честным статусом непроведённой приёмки и добавить упорядоченную ссылку в корневой README; проверить существование цели и отсутствие дубликата.
- [x] 1.2 Создать `docs/project-structure.md`, сверив роли каталогов, связи и пути Weeks 4–6/Day 31 с исходниками; проверить все упомянутые локальные пути, не описывать ещё отсутствующие компоненты как реализованные.
- [x] 1.3 Создать `day-31-developer-assistant/corpus.json` с ровно пятью источниками proposal и Day 31 corpus adapter; offline-тестами проверить exact allowlist, отсутствие link crawling, duplicates/missing/UTF-8/size/path boundaries и symlink/junction rejection.
- [x] 1.4 Добавить `mcp==2.2.0` в backend requirements и минимальный пакет Day 31; проверить установку в backend environment, `pip check` и независимый импорт старого backend без запуска MCP/Ollama/FastAPI.

## 2. Single-strategy index and retrieval

- [x] 2.1 Собрать structure-aware chunks существующими функциями Week 5 и embeddings через существующий адаптер; fake embedder тестами проверить одну стратегию, batches, provenance/строки/Unicode и отсутствие исторических baseline ограничений, включая корпус меньше пяти chunks.
- [x] 2.2 Реализовать отдельный SQLite snapshot Day 31, проверку hashes/config/vectors и atomic publication; temporary DB тестами подтвердить roundtrip, отказ на corruption/nonfinite/dimension mismatch и сохранность предыдущего индекса при embedding/write/replace failure.
- [x] 2.3 Добавить explicit build/no-op и freshness для документов, allowlist и config, включая повторную проверку перед публикацией; offline-тестами проверить edit/delete/approved addition, no-op без API, отсутствие влияния excluded files и отказ при изменении документов во время build.
- [x] 2.4 Подключить cosine retrieval до восьми chunks без старого threshold и одобренное сохранение введения основного документа вместо слабейшего hit; фиксированными векторами проверить hits, tie order, source_intro/cosine_rank и точный контекст generation/citations.

## 3. Real local Git MCP

- [x] 3.1 Реализовать stdio launcher/server и `get_current_branch` с пустыми arguments и strict output schema; проверками подтвердить read-only annotations, rejection неожиданных аргументов и фиксированный repository root без shell-команд из пользовательского текста.
- [x] 3.2 Реализовать серверное чтение Git branch/unborn/detached с timeout и безопасными ошибками; тестами подтвердить корректные состояния и отсутствие ложного detached при missing Git/not-repository/failure.
- [x] 3.3 Реализовать MCP client с initialization, paginated discovery, `call_tool`, strict result validation и собственным lifecycle; тестами проверить missing tool, `is_error`, malformed result, timeout/disconnect и закрытие процесса без передачи OpenAI key.
- [x] 3.4 Добавить real-process integration test: создать временный Git repo, вызвать настоящий stdio server, проверить обычную ветку, её смену, unborn и detached состояния, соответствие call_id/PID серверному stderr event и завершение процесса; пройти тест без OpenAI и network MCP.
- [x] 3.5 Проверить сценарий недоступного сервера через CLI/service boundary: тест должен получить ошибку MCP, ноль embedder/LLM calls и отсутствие прямого Git/`.git/HEAD` fallback; проверить code boundary review, success/error/cancellation cleanup и отсутствие raw stderr/секретов в диагностике.

## 4. Help command and grounded output

- [x] 4.1 Реализовать CLI `index`, `/help`, `--help`, `/help` без вопроса и `--trace` с фиксированным root и exit codes design; parser/CLI-тестами проверить вызов из другого cwd, неверный ввод и отсутствие API/MCP side effects у справки.
- [x] 4.2 Собрать последовательность freshness → MCP → query embedding → Top-8 → один Responses request с Day 31 instructions/schema и отдельным Git context; fake clients тестами проверить actual payload, model/budgets и ровно один embedding/максимум одну generation без retries/rewrite/judge.
- [x] 4.3 Подключить существующую grounded validation и renderer с отдельным Git-блоком и источниками/строками/цитатами; тестами проверить supported/insufficient_context, неверный chunk/path/quote, incomplete/refused/provider error и отсутствие успешного показа невалидного candidate.
- [x] 4.4 Добавить безопасный trace фактических retrieval и MCP-событий; тестами проверить ranks/scores/fingerprint, call_id/PID/event correlation, отсутствие секретных sentinel values/raw prompt/env/stderr и неизменность числа provider calls при включении trace. Сохранить JSONL по умолчанию и добавить `--trace-format text`; проверить Unicode, компактность, доступный usage и неизменность основного ответа в обоих форматах.

## 5. Documentation and offline acceptance

- [x] 5.1 Дополнить backend/scripts README настройкой, командами Day 31, freshness/errors и scoped test command; проверить команды и ссылки, исключить дублирование длинных инструкций в Day README и подготовить окончательный индексируемый корпус перед live.
- [x] 5.2 Выполнить три Day 31 test files и focused regression `test_document_indexing.py`, `test_first_rag.py`, `test_grounded_rag.py`, `test_agent_adapter.py`, `test_stateful_rag.py`; записать фактические результаты в OpenSpec `validation.md`, при сбое исправить причину и повторить затронутые проверки.
- [x] 5.3 Проверить синтаксис новых Python-файлов, JSON manifest, scoped diff, отсутствие секретов и изменений старых данных/контрактов; отдельно подтвердить корневую ссылку Day 31 и то, что SQLite/evidence исключены из Git. JVM/UI/Gradle и старые OpenSpec repairs не запускать без связанной причины.

## 6. Live acceptance and short video

- [x] 6.1 После успешных offline/integration-проверок явно построить индекс реальных пяти документов, проверить provenance и повторный `index` как no-op без API; записать fingerprint/config и usage сборки в `validation.md`, не раскрывая credentials.
- [x] 6.2 Выполнить Q1–Q4 из design, сохраняя при необходимости вывод в ignored Day 31 acceptance directory; вручную проверить факты, существенные утверждения, поддержку цитатами, пути/строки, MCP trace и отрицательный insufficient_context. В `validation.md` записать PASS/PARTIAL/FAIL каждого вопроса; при ошибке повторять только проверки с изменившимися входами/поведением.
- [x] 6.3 Подготовить для пользователя воспроизводимые команды и порядок видео из design (corpus/index no-op, Q2 с trace, Q4, итог тестов), опираясь на выполненные проверки; проверить шаги по имеющемуся выводу, явно отличать сохранённый replay от нового live. Запись видео пользователем не подменять утверждением об автоматической записи.
- [x] 6.4 Обновить Day README только фактическими результатами, проверить наличие корневой ссылки и окончательную актуальность индекса после правок разрешённых документов; сверить критерии готовности и OpenSpec validation. Не отмечать непроведённые проверки как выполненные; остановиться без автоматических commit/push/archive.
