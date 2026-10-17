# Техническая проверка Day 34

## Проверенная конфигурация

2026-10-17: Python 3.14.7, OpenAI SDK 2.54.0, requested model `gpt-5.6`,
в наблюдавшихся Responses — `gpt-5.6-sol`. Импорты подтверждены из нового worktree.
Выполнен один smoke, первоначальные сессии A/B и один независимый повтор B.
Всего 30 model requests: 2 + 10 + 9 + 9. При review/apply/verify API не вызывался.

## Настоящий protocol smoke

PASS: 2 запроса, `tool_choice=auto`, один native `list_files`,
`call_id=call_D5O0PGl5o3DJGT9XjsRAumAy`, matching function_call_output,
финальный ответ с двумя правильными именами файлов.
Evidence: `backend/.local/day34/smoke/20261017T113150Z/smoke.json`.
Это отдельная проверка протокола, не доказательство самостоятельности продуктовых сценариев.

## Offline

Итоговый целевой прогон: **86 passed**, 12.91 s.
Проверены реальные filesystem create/update, confirm/reject, stale source/target/candidate,
побайтовая неизменность до подтверждения, receipt/readback, повторное применение и
неоднозначный исход. Проверены native Responses-shaped items и call_id continuation,
альтернативные порядки, неверные/дублированные аргументы, неизвестные инструменты,
provider errors без retry, budgets/timeout/deadline, размеры, UTF-8, sources/lines,
недоверенный текст, повреждённая/неполная трасса, путь вне root, traversal, Windows-special
paths, symlink, настоящий Windows junction, reparse attributes и hard links.
Для этих тестов API не использовался; записи выполнялись только в test workspace.
Синтаксис восьми новых Python-файлов проверен без генерации bytecode.

Runner проверен по коду: он не читает scenario ID и не содержит маршрута A/B.
Scenario используется только при подготовке входов и независимой проверке.
В контекст модели не подставляются заранее прочитанные исходники или expected facts.
Verifier раздельно показывает доказанные вызовы/ссылки и недостающий критерий поиска;
недостающие evidence не заменяются PASS.

## Live A: новый отчёт

Run: `86cc3b13-0537-4c91-94af-c75b6ef496b9`.
Candidate: `2516d51311dd62c40ab79e9bb7e100659b79693bf3c9b04bfe83fce08f279905`.

10 model requests, 9 tool calls:
`list_files -> search_text -> search_text -> search_text -> search_text -> read_file -> read_file -> read_file -> stage_file`.

Поиск последовательно использовал буквальные запросы `app.first_rag.core.search`,
`first_rag.core`, `def search`, `search(`. Прочитаны все три исходника.
Действия и аргументы инициировала модель; приложение не перестраивало маршрут.

Native calls/call IDs, сохранённая цепочка requests/results, ссылки, хеши и
неизменность исходников — PASS. Сверка существенных фактов по коду:
определение, два импорта/вызова, descending cosine с tie-break, developer
full ranking/top-8/intro replacement и support observations/top-2 описаны корректно.
Охват явно ограничен тремя файлами. Ссылки корректны, но многие диапазоны широкие
(например, core.py:1–135); это ограничение точности навигации, не неизвестный источник.

## Live B: обновление документа

Run: `78fb1325-0616-4d01-8aa3-51fb19d9e3d7`.
Candidate: `051b59b61ed6a5994ea17a625859b6c9aa17ca90bc70d05c7af56bdcef3ed80e`.

9 model requests, 8 tool attempts:
`list_files -> read_file -> read_file -> read_file(error:size) -> read_file -> read_file -> read_file -> stage_file`.

После отказа читать developer service целиком модель сама выбрала диапазоны 1–130
и 121–169. Старый документ и все три исходника прочитаны.
Native calls/call IDs, связи request/output, ссылки и неизменность — PASS.
Сверка по исходникам: исправлены ascending ranking, одинаковый top-k=5 и отсутствие
observations; описаны top-8/intro и top-2. Раздел «Область применения» сохранён
побайтово, границы выборки обозначены.

**PARTIAL:** модель не вызвала `search_text`. Поэтому утверждённый отдельный
критерий multi-file search для B не пройден: `NOT_OBSERVED`, verifier status
`partial_review`. Прямое чтение достаточно для сформированного описания, но это
не заменяет предусмотренный критерий. Первоначальная трасса сохранена без изменений.
Разрешённый повтор ниже проверяет воспроизводимость, а не подменяет этот результат.

## Подтверждённое применение A и B

Пользователь рассмотрел оба документа/diff, дал содержательную оценку PASS
и явно подтвердил ровно перечисленные candidate IDs. Перед записью повторно
проверены ID, payload hashes, diff, initial inventory и хеши источников.
Выполнены штатные CLI review и apply в интерактивном терминале; на запрос
каждого apply введён соответствующий полный candidate ID. Механизм подтверждения
не изменялся и не обходился.

| Run | Запись/readback | Фактический SHA-256 docs/search.md | Receipt |
|---|---|---|---|
| A | PASS | `772c5d2ae54353aa91c0bc95fcd87dc3657249257c556cac865d9d2a20f9886f` | `runs/86cc3b13-0537-4c91-94af-c75b6ef496b9/receipt.json` |
| B | PASS | `61fae9fd97e36f8549ffff8760754937626cc63c6717b31d0c0b218d2fd7d799` | `runs/78fb1325-0616-4d01-8aa3-51fb19d9e3d7/receipt.json` |

Пути receipts указаны относительно backend/.local/day34/. Оба receipts имеют
status=applied, точный подтверждённый candidate ID, path=docs/search.md,
указанный sha256 и sources_unchanged=true. Decision каждого run — approve
того же ID. Фактические байты независимо прочитаны с диска и совпали с candidate.md.
Inventory подтвердил изменение только docs/search.md внутри каждого workspace.
Три Python-исходника как в копиях, так и в исходном worktree сохранили SHA-256.

Независимый verifier: A — verified_write, B — partial_review; native calls,
call IDs/provenance, citations, sources_unchanged и write — PASS у обоих.
У B multi_file_search остаётся NOT_OBSERVED. Пользовательский содержательный
PASS зафиксирован отдельно: автоматическое semantic_facts=REVIEW_REQUIRED
не выдаётся за автоматическое доказательство смысла.

API-трассы первого A/B не изменились после review/apply/verify:
- A events.jsonl: `50d57b8163b8eef5b8574644ba4696d784d687f328be11a6fdc145eeab2d0a27`, 10 запросов;
- B events.jsonl: `9165ee8208d3d15273307aa78c67b95854dd7704c9b1f4cac46a084db9a6c99f`, 9 запросов.

Post-write отчёты сохранены отдельно как verification-after-apply.json;
первоначальные verification.json, candidates, diff и native traces не переписаны.

## Независимый повтор B

Run: `a32ed8af-f594-4545-b880-07ea0b16d6cb`.
Candidate: `d63ba208faa82601283b6a7e27776ab11f0f889bec867830e73ebf46dc942ac5`.
Content SHA-256: `b30137bd24aacb47ed1b106aacdbbe97ec8dadc299dee66a436c83dbc2d91bc0`.

Подготовлена новая копия из исходного устаревшего Markdown, а не из применённого
документа B. До генерации побайтово сверены три исходника и base Markdown.
Цель, revision, source/manifest/fixture hashes, prompt version day34-files-v1,
instructions, schemas, SDK, лимиты и все model settings совпали с первым B.
Порядок инструментов не задавался, search_text не навязывался.

9 model requests, фактическая модель gpt-5.6-sol, 8 tool attempts:
`list_files -> read_file(docs/search.md) -> read_file(core.py) -> read_file(service.py, error:size) -> read_file(service.py:1-130) -> read_file(service.py:121-169) -> read_file(rag.py) -> stage_file`.
Наблюдавшиеся call IDs:
`call_OSgHgoynY1k1ImpSIpYAgvBf`, `call_eDJgiG9GPR4oK5aoxfmzXuj6`,
`call_MN2jjGfQsVDM14qVR3HsAa7w`, `call_YKj8cdRsMVxpyfRhQ9zwT8Jr`,
`call_wgHqQLgNsv3ztsZxo5ksSWVa`, `call_mgqeSXnj3XR3NV7kuhGok4Xw`,
`call_bMr8xmmtsCOBCAJa2h2SYfNZ`, `call_Ki5wojl7BZDwUcEDBafcucZ5`.
Response IDs отличаются от первого B; native calls/results/continuation проверены.

| Критерий | Сравнение первого и повторного B |
|---|---|
| Ранжирование | Совпало: descending cosine; tie-break source/ordinal/chunk_id |
| Developer | Совпало: полный рейтинг, префикс [:8], возможная intro replacement |
| Support | Совпало: вопрос + известные observations; min(2, число фрагментов) |
| Источники | Те же три файла, те же четыре диапазона/evidence и SHA-256; ссылки проверены |
| Полезный раздел | «Область применения» сохранена побайтово в обоих кандидатах |
| Границы | В обоих явно ограничена проверенная выборка |
| Текст | Различается; буквальное совпадение не требовалось |
| search_text | Не наблюдался в обоих; NOT_OBSERVED/PARTIAL сохранён |

Существенные факты совпали при технической сверке по коду. Замечание точности
повторного кандидата: фраза «восемь лучших результатов» не уточняет, что [:8]
возвращает до восьми при меньшем индексе. В первом B было «обычно ... восемь».
Это замечание сохранено для review, текст кандидата не исправлялся задним числом.

Verifier повтора: partial_review; native_calls/citations/sources_unchanged=PASS,
multi_file_search=NOT_OBSERVED, write=NOT_APPLIED. Goal/config/evidence comparison
сохранён в comparison-to-first-B.json, verifier — в verification.json нового run.
Новый run находится в awaiting_review; цель равна исходному fixture,
decision и receipt отсутствуют. Новое пользовательское подтверждение не получено,
кандидат не применён.

## Первоначальный статус приёмки

Задача 4.3 выполнена: один независимый повтор B проведён и сопоставлен с первым.
Задача 4.2 остаётся PARTIAL по предусмотренному критерию поиска B, несмотря на
содержательный PASS пользователя и успешную проверенную запись A/B.
Критерии не ослаблялись; первоначальный NOT_OBSERVED не заменён на PASS.
Итого 9/10 задач, полная процессная приёмка пока не объявляется.

## Пересмотр критерия 4.2 и итоговая приёмка

2026-10-17, после review первоначальных критериев пользователь явно разрешил
уточнить design/spec/tasks. Исходно требовался search_text по нескольким файлам
в обоих сценариях. В B это исключало достаточное самостоятельное исследование
через прямое чтение известной тройки исходников. Такой обязательный выбор
инструмента чрезмерно ограничивал цель проверки самостоятельных действий модели.

Уточнённый критерий: A обязан показать настоящий search_text, чтение трёх
исходников и новый документ; B — самостоятельное чтение трёх исходников и
старого Markdown, исправления и сохранение «Области применения». Для B
search_text необязателен. Native function calls/call IDs, корректные evidence,
staged candidate/diff, отдельное подтверждение конкретной версии, проверенная
запись и неизменность исходников обязательны для обоих первоначальных запусков.

Повторная независимая проверка сохранённых данных выполнена без API, с
запрещёнными socket connections в проверочном процессе. Verifier подтвердил
native calls, полную цепочку call_id/results/следующего запроса, чтение трёх
исходников, citations и неизменность источников у всех трёх запусков. Для A/B
подтверждены decision=approve нужного ID, candidate/diff integrity, readback,
receipt и изменение исключительно docs/search.md. SHA-256 совпали с таблицей
выше. У повтора B write=NOT_APPLIED; decision/receipt отсутствуют, цель осталась
исходным fixture. Все сохранённые файлы трёх runs после проверки неизменны.

| Условие уточнённого критерия | A | Первый B |
|---|---|---|
| Самостоятельные native calls, без маршрута runner | PASS | PASS |
| Чтение трёх исходников и evidence/ссылки | PASS | PASS; также прочитан старый Markdown |
| search_text | PASS | NOT_OBSERVED; теперь необязателен |
| Новый отчёт / исправления и полезный раздел | PASS | PASS по сверке с кодом и содержательному review пользователя |
| Кандидат, diff до подтверждения, точный одобренный ID | PASS | PASS |
| Запись, readback, SHA-256, receipt, unchanged sources | PASS | PASS |
| Приёмка по уточнённому критерию | PASS | PASS |

Сверка содержания с неизменёнными исходниками подтвердила определение и два
потребителя search, descending cosine/tie-break, developer полный рейтинг и
префикс [:8] с возможной intro replacement, support query с observations и
min(2, len(chunks)). B исправляет исходные неверные утверждения и сохраняет
контрольный раздел побайтово. Полнота в обоих документах ограничена выборкой.

4.2 отмечена DONE только после этой проверки; итог 10/10 задач. Это изменение
критерия приёмки, а не появление нового события в trace. Первый B и повтор B
по-прежнему имеют search_text=NOT_OBSERVED; прежний и текущий консервативный
verifier возвращает partial_review. Эти диагностические статусы, первоначальные
результаты, trace, candidates и receipts не переписывались. Реализация verifier
не изменялась; итог уточнённой приёмки является отдельным review сохранённых
доказательств. Автоматическое semantic_facts=REVIEW_REQUIRED также сохранено.

Повтор воспроизвёл существенные факты и полезный раздел, но формулировки
различаются; его неточное «восемь» вместо «до восьми» не исправлялось и остаётся
замечанием. Кандидат повтора не утверждён и не применён. Проверка маленькой
выборки и двух B-прогонов не доказывает общую надёжность, буквальную
детерминированность или семантическую правильность будущих документов.

При корректировке использованы прежние успешные 86 offline-тестов
(`python -B -m pytest backend/tests/test_day34_files.py backend/tests/test_day34_runner.py -q -p no:cacheprovider`):
код, тесты и model config после этого прогона не менялись. Повторно выполнены
AST-проверка восьми Python-файлов, независимый verifier, readback/receipt,
сверка 24/24 исходных пользовательских файлов с baseline и корневой ссылки.
Новые LLM-запросы, эксперименты и изменения функциональности не выполнялись.

## Изоляция Git

Работа выполнена в отдельном worktree, ветка codex/day34-project-files-assistant,
база f4651f54e90251a3a293708d65b81cb647b393ec. Финальная сверка baseline подтвердила
неизменность 24 путей и SHA-256 пользовательских правок Days 28–30, их status,
ветки main, HEAD и пустого staged-состояния основного дерева.
Изменены только файлы нового компонента, его тесты/данные/документация и change.
Сканирование 21 изменённого/нового файла не обнаружило значений credentials
или включённых локальных runtime-файлов. Strict OpenSpec validation прошла.

## Ограничения

Лексический поиск не разрешает произвольные dynamic/alias uses. Локальные
Markdown line anchors проверяются программой; viewer может их не поддерживать.
Ссылки в candidate.md рассчитаны на положение целевого docs/search.md внутри
workspace; для просмотра до apply используйте path/line из metadata и verifier.
Трасса доступна для независимой инспекции, но не имеет подписи провайдера.
Локальные path/hash checks не являются ОС-песочницей против конкурирующего
злоумышленника. Совпадение формальных evidence не доказывает смысл всех будущих
ответов модели.

## Проверка перед публикацией

После уточнения критерия выполнена strict non-interactive validation change —
PASS. Capability project-files-assistant синхронизирована в main spec:
Purpose и все девять требований/сценарии сверены с delta, operation headers
заменены обычным Requirements. Strict validation всех 52 main specs — PASS.
Затем штатный CLI архивировал только этот change в
openspec/changes/archive/2026-10-17-day-34-project-files-assistant/.
Архивирование использовало --skip-specs, поскольку синхронизация была уже
выполнена и независимо проверена; validation не отключалась.

Scoped review охватывает 22 файла Day 34, тестов, README и OpenSpec.
Проверки whitespace, секретов и запрещённых локальных данных — PASS.
Runtime, .env, рабочие копии, кандидаты, receipts и локальный HTML-viewer
остаются вне Git и не удалялись. Изменений Days 1–33 и активных changes
Days 28–30 в scope Day 34 нет. Перед Git-записью подтверждены исходные
24/24 SHA-256, status, main HEAD/ветка и пустой index основного checkout.
