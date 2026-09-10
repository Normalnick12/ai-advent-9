# Day 09 — Verification

## Итоговый live experiment

Источник результатов — последнее явное подтверждение пользователя после
исправлений deterministic verifier. При оформлении этого отчёта новых
live/provider calls не выполнялось.

### Normal compression

После четырёх confirmed turns для последнего normal response подтверждено:

| Метрика | Значение |
| --- | --- |
| Summarized messages | 2 |
| Raw tail в отправленном context | 4/4 |
| FULL preflight input | 3485 tokens |
| COMPRESSED preflight input | 1907 tokens |
| Signed delta | 1578 tokens |
| Уменьшение response context | 45.3% |

Compression реально использовалась для response context; полная confirmed raw
history сохранена. Эти preflight metrics относятся к context перед последним
normal generation, а не к новому context после commit четвёртой пары.

Maintenance summarization имела отдельные actual usage/cost, что пользователь
подтвердил вручную. Их численные значения в сообщении не переданы. Численный
compare-preparation overhead и общее число generation calls также не сообщены;
плановые восемь вызовов не выдаются за фактически наблюдаемое количество.
Нельзя выводить net денежную экономию только из response input delta.

### Итоговый quality compare

FULL response:
`identifier=unknown, limit=37, responsible=Мира`

COMPRESSED response:
`identifier=unknown, limit=unknown, responsible=Мира`

| Ветка | Factual preservation | Actual input | Output | Estimated cost, USD |
| --- | --- | --- | --- | --- |
| FULL | 2/3 | 3533 | 13 | 0.00053775 |
| COMPRESSED | 1/3 | 322 | 14 | 0.0000567 |

N/3 измеряет сохранение только identifier=ORBIT-7319, limit=37 и responsible=Мира.
Это не оценка общего качества текста. FULL baseline сам не сохранил identifier.
COMPRESSED сохранил responsible, но потерял limit, сохранённый FULL. В этом
прогоне input существенно уменьшился вместе с потерей части точной информации.
Это наблюдение одного прогона, не утверждение, что compression всегда ухудшает
quality. Normal preflight counts и compare actual usage относятся к разным
операциям и не смешиваются.

### Restart и reset — подтверждены

Пользователь вручную подтвердил:

- session восстановлена; conversation count=4;
- старые bubbles не восстановлены;
- runtime measurements и compare results очищены согласно design;
- restore не выполняет paid replay.

Task 9.4 закрыта по подтверждённому live experiment и пределам данных выше.
Task 9.5 закрыта по дополнительному ручному подтверждению пользователя:
durable summary после restart успешно прочитана, reset выполнен успешно,
старый диалог после reset не восстанавливается. Все 36 tasks закрыты.
При оформлении подтверждения новых provider calls не выполнялось.

## Исправления verifier — история диагностики

Первоначальный parser ожидал отдельную строку на каждое named field.
Ответы через запятые ошибочно получали 0/3; завершающая точка в Мира. затем
выявила второй edge case. Оба implementation bugs исправлены и покрыты
regression tests. Старые ошибочные 0/3 и оценки до punctuation fix исключены
из итогового quality result.

Ранние предоставленные для диагностики тексты содержали ORBIT-7319 в FULL;
их offline-переоценка дала 3/3 и 1/3. Это другие тексты, а не итоговый compare
выше. Финальный подтверждённый FULL содержит identifier=unknown и оценивается 2/3.

Verifier принимает переносы строк, запятые, semicolon, несущественные пробелы
и одну конечную sentence period. Значения сравниваются точно; 137, 037, 37.0,
другие имена, unknown/missing/conflicting duplicate fields не засчитываются.
Contamination validation и unavailable score для error/incomplete/refused
branches не изменены. Substring matching и LLM-as-judge отсутствуют.

## Offline verification

Результаты последних проверок соответствующего кода, выполненных до этой
документационной правки:

| Проверка | Результат |
| --- | --- |
| FullHistory seam до включения Day 09 | 81 passed |
| Targeted verifier/compression/boundary suite после punctuation fix | 95 passed |
| Полный backend regression после punctuation fix | 278 passed |
| Android JVM | 64 passed, zero failures/errors |
| Полный Android UI | 31 passed, zero failures/errors |
| Debug APK | BUILD SUCCESSFUL |

Backend tests используют fake clients и временные реальные SQLite databases.
Проверены strict tail, raw preservation, atomic summary/pair failure boundaries,
reopen/delete rollback, startup cleanup, isolation, signed counts, parallel
side-effect-free compare, contamination и exact verifier. Единственное backend
предупреждение — существующая Starlette/httpx deprecation.

UI tests используют fake repositories на Pixel 3a API 34. Проверены nested Back,
recreation, drafts, unknown-outcome recovery, partial compare, portrait/landscape
и large font/IME. Обнаруженное clipping composer исправлено; старый Day 08
font-scale test перенесён на локальный Compose override после двух зависших
instrumentation runs. Финальный полный набор прошёл без skipped tests;
production UI Day 08 не менялся.

В предшествующем документирующем проходе успешно проверены offline scores предоставленных
ответов, арифметика delta, структура/ссылки Markdown, strict OpenSpec validation
и scoped diff/status. Рабочий каталог содержит незакоммиченные изменения Day 09.
Исходный код не менялся; успешные backend/JVM/UI/build
проверки повторно не запускались. Commit, push и archive не выполнялись.

## Завершение Day 09 — 2026-09-10

По явному запросу `$finish-day Day 09` выполнены синхронизация пяти capabilities
с main specs и архивирование change; все 36 tasks завершены, включая ручную
проверку чтения summary после restart и удаления диалога после reset.
Strict validation change перед архивом успешна; после sync main specs:
14 passed, 0 failed. Проверено соответствие всех delta requirements основным
спецификациям с сохранением прежних сценариев.

Backend/JVM/UI/build результаты выше переиспользованы из текущей рабочей сессии:
после них соответствующий код не менялся. Новых live/provider calls нет.
Финализация включает отдельные проверки diff, Markdown-ссылок, состава файлов
и staged snapshot перед обычными commit/push по workflow finish-day.
