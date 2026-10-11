## Final disposition — 2026-10-10

Реализация и offline-проверки завершены: **222 passed / 1 skipped**.
Локальные embeddings, SQLite и vector/FTS5 retrieval работают в проверенной Windows-среде.
**26/28 tasks выполнены**; change остаётся активным и незаархивированным.
Задачи 5.5 и 5.7 не закрываются по факту принятия пользователем отчёта:
смысловое A/B-сравнение не завершено, actual Mac M1 остаётся PENDING.
Повторные inference-запуски Day 28 прекращены по решению пользователя.
Открытая инфраструктурная проблема загрузки Ollama (причина неизвестна),
незавершённая semantic verification и Mac-проверка передаются как ограничения в Day 29,
без изменения runtime и без объявления semantic PASS.

## 1. CLI compatibility and Knowledge selection

- [x] 1.1 Добавить routing knowledge/search/explain и --knowledge > LAA_KNOWLEDGE; проверить help/TTY/EOF/exit codes, none игнорирует environment Knowledge без SQLite/embeddings, legacy prompt/schema неизменны, обычный explain не требует preview/status/search.
- [x] 1.2 Реализовать bounded directory discovery и selection (--include, --exclude, --all-markdown) с показом relative paths/exclusions; проверить Markdown-only, hidden/service exclusions, links/junctions/traversal/ADS/Unicode, недоступные пути и все file/corpus/discovery limits в temporary directories.
- [x] 1.3 Реализовать preview/diff, явное принятие first/new/deleted/policy selection через TTY или --yes и сохранение approved policy/set; проверить cancel/non-TTY без writes/HTTP, повторное использование policy и обновление changed-only без лишнего вопроса.
- [x] 1.4 Проверить каноническую раздельность Knowledge/Workspace и безопасность index/state path; tests подтверждают отказ при равных/вложенных roots, links/reparse points в .laa/index и отсутствие чтения Kotlin до отказа.

## 2. Markdown provenance and persistent index

- [x] 2.1 Адаптировать чистые Markdown slicing/hash helpers Week 5 с указанием происхождения без backend imports; проверить ATX nesting, short documents, repeated headings, fenced fake headings, BOM/CRLF/LF coordinates, oversized fallback 1800/180 и сохранность source slices.
- [x] 2.2 Создать компактный SQLite schema с source/chunk provenance, float32 vectors, configuration fingerprints и FTS5; проверить capability probe, serialization/dimensions/non-finite/zero vectors, counts/foreign keys/hash consistency, unsupported schema и reopening.
- [x] 2.3 Реализовать атомарный full rebuild и unchanged no-op; проверить, что API/validation/disk failure, source changes before commit и busy writer не публикуют partial/mixed snapshot, прежний committed index сохранён.
- [x] 2.4 Реализовать freshness на candidate set и content hashes для status/search/explain; тесты покрывают same-size/same-mtime edits, added/deleted docs, unreadable source, excluded changes, policy/chunker mismatch и отказ до inference. Проверить перенос K вместе с .laa в другой root и read-only query.

## 3. Local embeddings and two search modes

- [x] 3.1 Расширить безопасный Ollama transport embedding capability/digest metadata и /api/embed; MockTransport проверяет truncate=false, bounded 8-item/64 KiB batches, 2 MiB responses, remote/proxy/redirect rejection, errors без content/retry и валидацию returned vectors.
- [x] 3.2 Реализовать embedding profile/fingerprint и query encoding с выбранным qwen3-embedding:0.6b default; проверить mismatch provider/model/digest/dimension/normalization/input recipe до vector use, запрет старых OpenAI/query vectors и explicit rebuild вместо смешивания.
- [x] 3.3 Адаптировать cosine search Week 5 и реализовать FTS5 literal-term text search по тому же snapshot; тесты проверяют ranks/ties/top-k 1..10, PaymentGateway/session_id, кириллицу, punctuation/NOT/quotes/SQL-like data, zero hits и отсутствие HTTP в text search.
- [x] 3.4 Реализовать CLI search и explain retrieval enrichment (question + filename stem + CamelCase words); проверить общий вопрос без имени класса, неизменность generation question, raw/enriched limits, rank/score/source/section/lines/ID/snippet, отсутствие generation/content writes в search и ошибки FTS5/stale.
- [x] 3.5 Добавить последовательный memory profile extended inference и документируемое управление keep_alive; MockTransport подтверждает последовательность batches/query/chat и отсутствие parallel/retry/config mutation, legacy options неизменны.

## 4. Grounded extended explanation

- [x] 4.1 Собрать общий extended prompt/schema для none/vector/text с code_observations, documented_rules, applications, assumptions, limitations и knowledge_status; проверить реальные payloads, одинаковые instructions/schema/settings для A/B и строго раздельные user-data fields для Kotlin/docs.
- [x] 4.2 Реализовать паковку целых ranked chunks в body <=24 KiB с Kotlin <=16 KiB, question <=2000, output <=256 KiB; проверить selected/omitted counts, minimal-body rejection, zero-fit error без chat, отсутствие code truncation и ссылки только на фактически отправленные chunks.
- [x] 4.3 Реализовать completion/schema/ID/line/exact-quote validation и раздельный render code/rule/application; тесты покрывают bool/out-of-range/duplicate lines, unknown/duplicate IDs, missing supporting refs, quote >400 или не из context, done!=stop, invalid JSON и отсутствие repair.
- [x] 4.4 Реализовать not_requested/no_candidates/candidates_provided и корректное признание недостатка знания; проверить пустые rules/applications для none/zero hits, limitation при unsupported context, code-only observations и отсутствие silent fallback при technical failure.
- [x] 4.5 Добавить integrated privacy/adversarial tests: injections/fake roles/commands в Markdown и Kotlin остаются данными, system instructions неизменны, нет tool/subprocess/external side effects и terminal escapes; sentinel code/question отсутствуют в storage/logs после success/failure. Зафиксировать, что mock tests не доказывают устойчивость LLM.

## 5. Experiment and portability verification

- [x] 5.1 Подготовить synthetic architecture Markdown, distractors и rubric для существующего CheckoutCoordinator.kt; до live зафиксировать вопрос, expected code facts/rules/source spans, forbidden claims, A/B settings и отдельный negative/adversarial case. Проверка — review fixture/rubric и покрытие spec acceptance criteria, без готового ответа в docs.
- [x] 5.2 Добавить узкий Week 5 fixture-preparation helper вне runtime CLI; read-only проверить pinned Day 21 run/corpus/source hashes и экспортировать только 9 Markdown snapshots в отдельную локальную K. Тесты подтверждают отсутствие старых vectors/backend imports/записи старой базы, safe destination handling, отказ при неверном/missing snapshot и отсутствие экспорта в Git/report.
- [x] 5.3 Выполнить offline suite общей утилиты (legacy + новые tests), syntax/import checks и integrated temporary-Knowledge flow; записать реальные counts/platform skips без backend/Android/Gradle запусков. Повторять только затронутые проверки после исправлений.
- [x] 5.4 После проверки controlled local-only Ollama и установленных моделей построить synthetic и Week 5 indexes локально; отдельно проверить vector/text retrieval на фиксированных cases и Q01/Q07/Q10, reopen/no-op/no re-embedding. Зафиксировать supporting-fact coverage, безопасные timings/settings и реальные failures без изменения старого index.
- [ ] 5.5 Провести одну новую A/B пару extended none/vector с общими model+digest/instructions/schema/8192-2048/think/temperature=0/seed=28 и один отдельный negative/adversarial live case; без retries/cherry-picking. Записать technical outcomes и content-free metrics, затем ручной review correctness/support/applicability/unsupported claims/uncertainty с reviewer identity; pending review не считать completed, неуспех честно обозначить.
- [x] 5.6 Подготовить переносимость: проверить отсутствие обязательных Windows dependencies, isolated OS guards, relocation/FTS5 tests, документировать macOS commands и memory profile; подтверждение — offline tests и инструкции, не actual Mac PASS.
- [ ] 5.7 На доступном Mac M1 16 GB выполнить focused tests и compact A/B, проверить FTS5/relocation/sequential profile/timings/memory/swap. При отсутствии устройства или запрете политики оставить PENDING / NOT TESTED и checkbox незавершённым; Windows acceptance и Day 29 не блокируются.

## 6. Documentation and scope review

Evidence: [validation.md](validation.md), 2026-10-10. Задача 5.5 остаётся открытой
(INCOMPLETE / BLOCKED): исходные A/B завершились timeout без ответов; в отдельном
[preload follow-up](diagnostic-followup-2026-10-10.md) получен только A, preload B
завершился timeout; [lifecycle experiment](lifecycle-experiment-2026-10-10.md)
остановился на начальном preload, оба chat не запускались. Полной A/B-пары нет.
Negative technical PASS / semantic PARTIAL (review ассистента), human review pending.
Исторические результаты сохранены; дальнейшие повторы прекращены.
Задача 5.7: actual Mac M1 PENDING / NOT TESTED; не блокирует Windows-часть/Day 29.

- [x] 6.1 Обновить README существующей утилиты с knowledge lifecycle, commands/selection approval, local-only prerequisites, FTS5/model profiles, text/vector semantics, byte/token limits, privacy и Windows/macOS setup; проверить команды/help и ссылки. Исторический Day 27 verdict не переписывать как результат Day 28.
- [x] 6.2 Добавить краткий day-28-local-architecture-rag/README.md («Суть эксперимента», «Что проверяет», «Результаты») и упорядоченную относительную ссылку в корневом README; проверить существование цели, отсутствие дубликатов, ссылку на общую утилиту и только фактические outcomes, включая pending Mac при необходимости.
- [x] 6.3 Проверить scoped diff/status, git diff --check, отсутствие secrets/private content/transcripts и изменений Weeks 1–5/Day 27 OpenSpec artifacts; выполнить OpenSpec strict validation и сверить все checkboxes с evidence. Представить implementation/offline/live/semantic/Mac outcomes отдельно; не выполнять archive, commit или push без отдельного запроса.
