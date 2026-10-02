## 1. Retrieval и сохранённый baseline

- [x] 1.1 Параметризовать shared cosine search с default Top-5 и поддержкой Top-10; проверить existing Day 22 tests и focused ordering/tie/vector checks без изменения baseline behavior.
- [x] 1.2 Добавить Day 23 config (N=10, K=5, threshold=0.50, rewrite settings) и загрузку pinned index/frozen baseline snapshot с calibration limitations; проверить совместимый fixture и отказ при несовпадении provenance/hash/config до provider calls, source artifacts не меняются.
- [x] 1.3 Реализовать один Responses rewrite только по original question и embedding exact retrieval query; fake-client tests подтверждают отсутствие ground truth в input, сохранность точного query, раздельные original/query и отсутствие retry/fallback при failed rewrite.
- [x] 1.4 Реализовать Top-10/filter/final context и все три decision reasons; focused fixtures проверяют equality 0.50, K-limit, unchanged cosine order и empty successful selection без fallback.

## 2. Staged CLI, generation и report

- [x] 2.1 Добавить `retrieve` и поэтапные JSON checkpoints в ignored `backend/.local/day23`; offline chain test подтверждает 10 rewrite + 10 embedding и 0 enhanced generation calls, actual input/output/status/usage и полный candidate evidence.
- [x] 2.2 Добавить однократный `compare` по saved retrieval с прежним generation CONFIG и ORIGINAL question; fake-client tests подтверждают 10 enhanced и 0 rewrite/search/embedding calls, полные kept texts/labels, empty context, failed prerequisites, сохранение incomplete/unknown и отказ от повторного compare.
- [x] 2.3 Добавить separate manual review template с двумя rewrite diagnostics/note, per-fact final-context/answer labels и enhanced grounded claims; проверить pending/unavailable/allowed labels и неизменность imported baseline review.
- [x] 2.4 Добавить offline `report` с video flow, per-fact baseline/enhanced comparison и technical/decision counts без общего score; subprocess test без key/index/original baseline подтверждает карточку/summary/full text, отсутствие provider calls и записи raw evidence.

## 3. Проверки, один live experiment и документация

- [x] 3.1 Проверить синтаксис изменённых Python files, CLI help и focused Day 23/Day 22 tests в existing backend environment; до live сохранить окончательные question/config snapshots и подтвердить отсутствие semantic pre-runs.
- [x] 3.2 Выполнить один frozen `retrieve`, затем один `compare` без повторных baseline/retrieval calls; проверить saved actual dispatch counts (при полном успехе 10 rewrite + 10 embedding + 10 enhanced), неизменность threshold/prompt и сохранность failures/empty context/regressions.
- [x] 3.3 Заполнить manual rewrite/per-fact/claim review Q01–Q10 по saved texts, различая rewrite/ranking/filter/assembly/generation причины; offline report подтверждает baseline/final context и baseline/enhanced answer labels, groundedness и calibration limitation без заранее заданного verdict.
- [x] 3.4 Создать краткий Day 23 README по шаблону, добавить одну упорядоченную ссылку в root README и команды/контракт в scripts/backend README; проверить существование link target, соответствие результатов evidence и offline report flow для видео без новых calls.
