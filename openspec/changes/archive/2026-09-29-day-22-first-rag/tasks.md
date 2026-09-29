## 1. Fixed corpus and questions

- [x] 1.1 Создать `day-22-first-rag/questions.json` по Q01–Q10 из design со stable fact ids, full acceptable source paths, difficulty и Q10 negative marker; проверить JSON schema, уникальность IDs, состав 5/3/1/1 и membership каждого path в pinned snapshot.
- [x] 1.2 Сверить expected facts с сохранёнными текстами Day 21 и Q10 с отсутствием утверждённых RPO/RTO; зафиксировать question-set version/hash до live и проверить, что expectations не зависят от будущих ответов модели.

## 2. Read-only index and retrieval

- [x] 2.1 Добавить Day 22 загрузку через существующий loader с pinned run/hash/strategy/config и валидацией selected chunk IDs/text hashes/vectors; проверить offline fixtures для missing/corrupt/incompatible index, отсутствие rebuild/document embedding calls и сохранность Day 21 DB.
- [x] 2.2 Реализовать query embedding исходного question совместимым adapter и brute-force cosine со stable ties и fixed Top-5; проверить известные normalized/unnormalized vectors, ties, dimension/nonfinite/zero norm и ровно один query call без threshold/filtering.
- [x] 2.3 Добавить CLI `search` с score/source/section/lines/preview и полными chunks по запросу; recording adapters должны подтвердить один embedding и ноль generation calls, прежний input без rewriting и отсутствие секретов в выводе.

## 3. Context and controlled generation

- [x] 3.1 Добавить общий input builder для direct (пустой context) и RAG (полные Top-5 blocks с provenance); проверить точное сохранение question/text/rank, независимость от сокращённого preview и отсутствие scores/vectors/expected facts/allowlist/difficulty/negative marker в model input.
- [x] 3.2 Настроить отдельный Day 22 AgentConfig с общей instruction, `gpt-5.6`, reasoning none, 600 output tokens и disabled truncation через существующий stateless generation path; recording client должен подтвердить одинаковые settings, отсутствие history/tools/retries и неизменность defaults старых дней.
- [x] 3.3 Добавить `ask --mode direct|rag` с явными completed/incomplete/refused/error outcomes; проверить, что direct работает без DB, RAG без валидного retrieval не dispatch-ится и ошибки/непригодные ответы не запускают retry или увеличение budget.

## 4. Evidence and full evaluation

- [x] 4.1 Добавить уникальный локальный eval directory и поэтапное сохранение frozen questions/config/index provenance, query vector, Top-5 full hits, actual inputs и outcomes/usage/counters без credentials; проверить round-trip, запрет overwrite и прекращение новых dispatch при недоступной записи.
- [x] 4.2 Реализовать `eval` для всех десяти questions с единственным retrieval и двумя независимыми generations на каждый question; fake run должен подтвердить 10 embedding + 10 direct + 10 RAG calls, unchanged config, отсутствие предварительных tuning calls, semantic retries, resume/replay.
- [x] 4.3 Покрыть integration failures: query embedding error, generation incomplete/refusal/error, interrupted attempt и evidence write failure; проверить truthful attempted/completed/not-dispatched/unknown, отсутствие RAG при failed prerequisite и сохранение независимых результатов без повторов.

## 5. Manual review and offline report

- [x] 5.1 Добавить отдельный manual review JSON/template с per-fact context/direct/RAG yes/partial/no, notes и groundedness yes/no для существенных RAG claims; проверить pending/null и unavailable, отсутствие semantic auto-grading и возможность разных outcomes внутри вопроса.
- [x] 5.2 Добавить только auxiliary `source_path_hit@5` и N/A для Q10; проверить fixture, где правильный path найден без expected fact, а также no-answer case, не классифицируемый автоматически как retrieval failure.
- [x] 5.3 Реализовать `report` с selector вопроса, retrieval-only/full-chunk просмотром и summary всех десяти по difficulty; subprocess/recording проверка должна подтвердить работу без key/DB/provider, отсутствие изменения raw evidence и порядок QUESTION → TOP-5 → DIRECT → RAG → EXPECTATIONS/REVIEW.

## 6. Documentation and offline readiness

- [x] 6.1 Добавить краткий Day 22 README по проектному шаблону, пока с явным отсутствием live результатов; добавить ровно одну относительную ссылку на него в корневом README после Day 21 и проверить существование target и отсутствие дубликата.
- [x] 6.2 Описать setup, точные CLI commands, pinned run, manual review и provider counts в backend/scripts README; проверить, что video flow использует report сохранённого eval и не требует предварительных semantic runs тех же вопросов, новых services или Android.
- [x] 6.3 Выполнить focused backend tests, проверки синтаксиса новых Python/JSON и затронутые существующие adapter/indexing tests при изменении shared code; записать фактические результаты и убедиться через git diff/status, что .env, DB, caches и local evidence игнорируются. Android/Gradle tests без Android изменений не запускать.

## 7. Single live run and observed results

- [x] 7.1 После успешных offline checks сверить frozen questions/hash, общий prompt/config, pinned run и доступность evidence directory, затем выполнить один полный live eval без предварительного semantic search/ask этих вопросов; сохранить реальные 10 query + 10 direct + 10 RAG outcomes либо честные technical failures/skips без retries и повторного eval ради лучшего результата.
- [x] 7.2 Вручную заполнить per-fact review и существенные RAG claims по сохранённым chunks/actual inputs/answers, различая retrieval, assembly, generation, faithfulness и coverage/no-answer; результатом должна быть сохранённая таблица с обоснованием оценок, без semantic evaluator или LLM judge.
- [x] 7.3 Проверить offline report выбранного local/cross-source вопроса, Q10 и summary десяти вопросов для видео без звука; подтвердить ноль новых provider calls и сохранение плохих/неполных результатов исходного run.
- [x] 7.4 Обновить Day README только фактическими наблюдениями этого набора и запуска, включая limitations и technical outcomes; проверить отсутствие общего вывода «RAG лучше», утверждений об оптимальности K/strategy, сохранность root README link и итоговый git diff/status без commit/push до отдельного запроса пользователя.
