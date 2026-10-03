## 1. Frozen retrieval и response contract

- [x] 1.1 Добавить isolated Day 24 replay loader над существующими index/baseline/search helpers; проверить все Q01–Q10 hits/scores и question/vector/config identity до generation, неизменность baseline и отказ на mismatch focused tests.
- [x] 1.2 Добавить best-score gate 0.50 и deterministic abstention; fake-client tests подтверждают отсутствие dispatch ниже порога, PASS при равенстве, сохранение полного Top-5/low-score chunk и отличие technical failures от insufficient_context.
- [x] 1.3 Добавить unified strict schema, краткий prompt/config с budget=3000 и context builder с full chunk IDs; проверить request payload, полные texts/metadata, отсутствие eval labels и status invariants для answered/обоих abstention origins.

## 2. Validation и evidence

- [x] 2.1 Реализовать strict parser и deterministic provenance/citation validation по spec; параметризованные tests покрывают пустой answer/arrays, unsent IDs, metadata/sets/duplicates, literal quotes/400-symbol limit, invalid abstention и отсутствие repair при validation_failed/normalized_result=null.
- [x] 2.2 Реализовать последовательный eval с run/Qxx checkpoints и сохранением raw output до validation; fake-provider/storage tests проверяют оба origins, dispatch evidence, unknown/refused/incomplete/error, запрет retries и остановку новых calls при ошибке сохранения.
- [x] 2.3 Добавить связанный с run review template/loader с отдельными mechanical/support/unsupported-claims/optional per-fact labels; tests проверяют pending/N/A/unavailable и exact-but-unsupported fixture без автоматического support=yes или общего score.

## 3. CLI и reports

- [x] 3.1 Добавить eval/report CLI, forensic --full и компактный --video с выбором Qxx; CLI tests подтверждают keyless/self-contained report, все секции answered, различимые runtime/model abstention и явный validation failure.
- [x] 3.2 Из каталога `backend` проверить интеграцию командой `.venv/Scripts/python.exe -m pytest tests/test_grounded_rag.py tests/test_first_rag.py tests/test_rewrite_filter_rag.py -q`, синтаксис новых Python файлов, CLI --help и отсутствие изменений поведения Days 22–23; устранить ошибки до live.

## 4. Frozen live evidence и документация

- [x] 4.1 Выполнить один live eval Q01–Q10 с зафиксированными prompt/schema/threshold/settings; сохранить все outcomes без tuning/retry, подтвердить 0 новых embeddings, ожидаемые 9 generation dispatches и Q10 attempted=false либо явно зафиксировать техническое прерывание вместо объявления полного run.
- [x] 4.2 Выполнить manual review всех десяти сохранённых outcomes по spec без LLM judge, отдельно отметить support/unsupported claims и correctness/coverage при необходимости; проверить reports Q05/Q07/Q08/Q10 и общий --video без новых calls, сохранить pending там, где реальная оценка не выполнена, и не закрывать task до её завершения.
- [x] 4.3 Создать краткий `day-24-grounded-rag/README.md` с фактическими результатами/ограничениями, добавить существующую относительную ссылку в раздел «Задания» корневого README, описать контракт/команды в backend/scripts README; проверить ссылки, отсутствие секретов/локального evidence в tracked changes, `git diff --check` и `openspec validate day24-grounded-rag --strict`.
