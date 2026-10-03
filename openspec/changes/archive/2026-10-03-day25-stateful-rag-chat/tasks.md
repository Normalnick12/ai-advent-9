## 1. Contracts and storage

- [x] 1.1 Реализовать строгие Day 25 memory/patch/combined payload models и pure validator/reducer по design; проверить fixtures для current-user provenance, corrections/removal, no-op, duplicates, invalid target и limits.
- [x] 1.2 Добавить изолированный Day 25 store с atomic commit_turn pair/result/memory/revision поверх existing SQLite primitives; проверить fault-injected rollback, exact reopen, isolation, stale revision и idempotent delete, сохранив Day 07 store tests.

## 2. Context retrieval and turn lifecycle

- [x] 2.1 Добавить fixed recent selection, deterministic contextual query и generation assembly с отдельными слоями; recording clients должны подтвердить exact actual inputs, отсутствие U1/U2 на U6 и вступление patch в retrieval только следующего turn.
- [x] 2.2 Подключить pinned Day 21/22 Top-5/embedding и Day 24 gate/grounding validation; проверить pinned mismatch/error handling, boundary 0.50, сохранение всех пяти chunks, source/citation membership и отсутствие rewrite/filter.
- [x] 2.3 Реализовать один Day25ChatService с combined generation, independent validation, abstention matrix и atomic persistence; fake-client tests должны покрыть оба invalid payload направления, valid-but-discarded abstention patch, refusal/incomplete/timeout/cancellation, busy и отсутствие retry/partial commit.
- [x] 2.4 Подключить отдельный FastAPI namespace и lifetime resources; API tests должны подтвердить create/read/send/delete, expected_revision, unknown/read-only restore, confirmed response fields и technical/unknown recovery без изменения прежних endpoints.

## 3. Frozen acceptance and saved report

- [x] 3.1 Создать scenarios.json с точными A/B scripts из design, per-turn expected facts, early-memory expectations и full pinned source/chunk anchors; offline validation должна подтвердить 6 user turns на сценарий, существование anchors и freeze/hash inputs до live.
- [x] 3.2 Создать CLI runner того же service с fresh isolated scenario stores, reopen после T3 и per-turn checkpoints/evidence; fake run должен подтвердить до 12 calls на сценарий, stop-on-failure без replay, сохранение raw output до validation и U6 mechanical checks.
- [x] 3.3 Реализовать keyless offline report и компактный --video с U1/U2, U6, recent positions, pre-U6 memory, actual query, retrieved sources и grounded answer; проверить saved completed/partial/abstained fixtures, pending review и unavailable без fabricated success.

## 4. Android thin client

- [x] 4.1 Добавить отдельные Day25 DTO/repository/ViewModel, CurrentSessionStore namespace и read-only restore/reconciliation; JVM tests должны покрыть confirmed sources/memory/count, skipped update, uncertain send без replay, missing/malformed identity и explicit reset после потерянного DELETE response.
- [x] 4.2 Добавить Day25 screen/navigation entry на ChatBubble/ChatComposer с sources, collapsible Task Memory и loading/error/session states; проверить через scripts/dev.ps1 unit/build и focused ui -Test по scripts README, включая доступность прежнего Day 07 screen.

## 5. Live evidence and documentation

- [x] 5.1 После успешных focused checks и freeze выполнить один live A/B experiment без emulator, retries/repair или изменения expectations; доставить saved run и фактический budget (до 24 calls), mechanical U6 acceptance либо явные failure/limitation/partial outcomes.
- [x] 5.2 Выполнить ручной review early memory patches и A5/A6/B5/B6 по expected facts, relevance, citation support и early constraints; записать reviewer identity/notes и повтор условий в recent assistant, без LLM judge или заявления exclusive causal benefit. Pending human review не отмечать completed.
- [x] 5.3 Подготовить saved --video report и короткую Android demonstration после проверки backend/emulator connectivity через scripts/dev.ps1 status; подтвердить отображение answer/sources/memory, demo calls учесть отдельно. Факт пользовательской записи видео не выдумывать.
- [x] 5.4 Добавить краткий day-25-stateful-rag-chat/README.md с проверенными результатами/ограничениями, component setup/run/report docs и упорядоченную относительную ссылку в корневой README; проверить target links, syntax/структуру, git diff --check и openspec validate --strict. Commit/push только по отдельному запросу.
