# Day 29 — compact-evidence-v1, live 2026-10-11

По отдельному разрешению пользователя выполнены ровно два chat-запроса: S4 → S6. Оба technical PASS. Предварительный semantic review: **S4 PASS по основной задаче отсутствующих знаний; S6 FAIL** из-за неверного ограничения LaunchedEffect и существенных пропусков. Reviewer: assistant provisional, совместный user review pending. Практическая пригодность профиля в целом не подтверждена, модель не выбрана.

Это отдельный schema + format-instruction experiment. Отклонённый explain-evidence-v1 не подключался. Исходные FAIL/PARTIAL и его length failure сохранены. Новый контракт не переносился в обычный CLI. Никаких preload, дополнительных генераций, retries, repair, новых prompt-правок или изменений runtime/settings не было.

## Preflight и идентичность

- Ollama 0.40.2: активный serve PID 9572 запущен 09:30:06, тот же server.log фиксирует OLLAMA_NO_CLOUD=true и cloud disabled=true. Listener только 127.0.0.1:11434. До metadata-запросов established connections не было.
- `/api/ps` пуст, процессов runner/llama и посторонних Python-клиентов не обнаружено. Исторический запрос завершился HTTP 200 и idle в логе. Это достаточные наблюдаемые признаки завершения предыдущей работы; API не предоставляет абсолютного доказательства отсутствия любой очереди/гонки с другим клиентом.
- Один GPU preflight, шесть измерений через 5 s: utilization **6 / 6 / 7 / 7 / 6 / 5%**, median **6%**; free VRAM **11392 / 11391 / 11392 / 11392 / 11402 / 11391 MiB**. Все условия v2 выполнены. Это проверка устойчивой фоновой нагрузки, не доказательство полного отсутствия конкуренции.
- Exact tag: `qwen2.5-coder:7b-instruct-q4_K_M`; digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
- Effective model profile `336fdb5fa73c6c7ba4ed39f1a454e1ff54295e774baad00b8d5ba0018ad2c007`, неизменен до/после серии. Q4_K_M, thinking not_supported. num_ctx=8192, num_predict=2048, temperature=0, seed=28, keep_alive=5m; остальные explicit/inherited settings сохранены в evidence.
- Compact prompt `7cf8f554d62d6372392bf56617ea40f1c7dfd3acc17b834106b86c3b00410177`, schema `f9a7bf9822f9e2ee1319e03fbd927f99cba412420c150b0f5b13fdb46f0a8ad8`, parent manifest `afb74eed9bfacf85576c53aeeee2b56be274446d21a5ff5c62dde789f08aa4d4` совпали с offline review.
- Frozen Kotlin/questions/chunks/order проверены. Для обоих случаев разница с baseline payload только в system message и schema. После серии hashes снова совпали; **74** защищённых файла, включая runtime-код, fixtures, manifests и исторические reports, не изменились.

Полные безопасные метрики: [evidence](compact-contract-live-evidence-2026-10-11.json). Полные ответы показаны в разговоре для review; в metrics/journal и этот отчёт автоматически не сохранялись. Использовались исключительно синтетические материалы.

## Технический результат и метрики

| Сценарий | Technical | Residency before | HTTP generation wall, s | Provider load, s | Prompt eval, s | Decode, s | Prompt / output tokens | Bounded client wall, s |
|---|---|---|---:|---:|---:|---:|---:|---:|
| S4 | PASS, done/stop | not resident | 4.897766 | 2.324269 | 0.267941 | 2.292719 | 1182 / 202 | 5.277739 |
| S6 | PASS, done/stop | resident | 9.969554 | 0.005139 | 0.205571 | 9.721700 | 1511 / 860 | 10.348584 |

Provider total: 4.896608 / 9.968332 s. Driver user_request (packing → response validation): 4.901307 / 9.973322 s. Provider load входит в HTTP wall; повторно не складывается. S4 включает холодную загрузку внутри chat, отдельный load-only admission не выполнялся. S6 — warm generation с фактически проверенной резидентностью. Deadline каждого дочернего клиента 180 s, не HTTP read timeout. Decode throughput по API eval_count/eval_duration: 88.105 / 88.462 tokens/s. TTFT unavailable (`stream=false`), retrieval=0, embeddings=0, полного RAG-запроса не было.

В S6 server.log показывает reuse 456 prompt tokens: API prompt_eval_count=1511 нельзя приравнять к 1511 заново вычисленным токенам; в логе eval 1055. Обе попытки: HTTP 200, slot release, truncated=0, all slots idle. После каждого ответа digest/context=8192 подтверждены, после серии `/api/ps` указывает runner=llamacpp, size=size_vram=5,133,943,438 bytes (~4896.11 MiB). Модель не выгружали вручную.

| Сценарий | System VRAM used до → после, MiB | System RAM available до → после, GiB |
|---|---:|---:|
| S4 | 587 → 5700 | 20.109 → 19.377 |
| S6 | 5700 → 5699 | 19.374 → 19.309 |

Это точечные before/after snapshots, не peak и не чистая память модели. Runner RSS/process commit unavailable. Windows-результаты ничего не доказывают о Mac M1; Mac NOT TESTED.

Schema/fields/types, допустимые уникальные Kotlin lines, selected chunk IDs, буквальность quotes и completion прошли parser. В S4 documentary applications пусты; проверять цитаты там не требовалось. В S6 три documentary applications, quotes из двух разрешённых compose chunks, дословные. Механическая допустимость строк не означает правильную смысловую привязку: ниже выявлены плохие ссылки. Ответ S4 имеет одно observation вместо запрошенных инструкцией 3–5; schema такого минимума не требует, смысловая оценка привязана к вопросу S4.

## Review по прежней rubric

### S4 — PASS по основной задаче, assistant provisional

| Критерий | Результат |
|---|---|
| Нет данных RPO/RTO | Correct: явное признание недостатка сведений |
| Нет придуманных значений/гарантий | Correct: значения, обещания восстановления и категорическое отрицание свойства не добавлены |
| Нерелевантные weather rules | Correct: documentary applications пусты, чужое правило не использовано |
| Kotlin facts | Correct в кратком описании последовательности; ранние возвраты не раскрыты, но вопрос S4 о RPO/RTO, не полный разбор checkout |
| Limitations | Корректная неопределённость RPO/RTO; лишнее замечание о неизвестности rollback не создаёт прежнюю причинную связь между rollback и RPO/RTO |
| Unsupported claims | 0 выявленных по основной задаче |

Появилось краткое объяснение своими словами вместо копии исходника. Это полезное улучшение для случая отсутствующих знаний, но один прогон не доказывает устойчивость и не закрывает качество всего инструмента.

### S6 — FAIL, assistant provisional

| Критерий | Результат |
|---|---|
| K1 ownership/delegation | Partial: роль ViewModel и Compose названа верно; private MutableStateFlow/asStateFlow, фактические пути load/onDetails и неизвестная реализация Coordinator не разобраны |
| K2 StateFlow | Missing: названа передача текущего state, но нет hot/current/initial value, equality conflation, отличия от event queue и process-death persistence |
| K3 lifecycle collection | Missing/misleading: API назван без STARTED threshold/остановки сбора и отличия от producer; ограничение о числе вызовов при изменении keys не объясняет lifecycle |
| K4 LaunchedEffect | Incorrect: observation верно упоминает запуск при изменении ключей, но limitations отрицает гарантию перезапуска при изменении ключей. Отмена при выходе из Composition, отмена старой coroutine при смене keys и same-key recomposition не объяснены |
| K5 cancellation/scopes | Missing: нет различия прямого suspend вызова и отдельного scope, кооперативной отмены, lifecycle STOP и ухода из Composition. Фраза об отмене при повторном входе смешивает разные события |
| K6 state transitions | Missing: нет loading=true → title, отсутствующей обработки исключений/отмены и возможности пропустить промежуточное состояние |
| R4 ownership rule | Верный scope и буквальные quotes; application в основном переводит правило, слабо связывает его с реализацией |
| R5 state/effect rule | Scope правил верен, но смысловая привязка недостаточна: application о StateFlow/collection ссылается на 14–16,45–47 вместо определяющих 27–28 и 43 |
| Неизвестные реализации | Partial: assumptions о наличии реализаций обозначены, но границы storage/network/cancellation не раскрыты |

Выявлен **1 явно неверный API-вывод** (нет гарантии перезапуска effect при изменённых keys) и **2 вводящих в заблуждение ограничения** (число вызовов collector в зависимости от keys; отмена при повторном входе вместо корректного описания выхода). Это не fabricated network/rollback/exactly-once guarantees, но ошибочное ограничение известного контракта API. Прежняя rubric относит lifecycle/execution ошибку к FAIL. Ссылки формально допустимы, однако не все поддерживают приписанное им утверждение.

Копирование Kotlin исчезло, но substantive explanation улучшилось лишь частично: описаны поля state и три роли, documentary applications в основном пересказывают Markdown. Главные механизмы StateFlow/lifecycle/effects всё ещё не объяснены, есть внутреннее противоречие. Число observations 3 вместо 1 само по себе улучшением не считается.

## Историческое сравнение и вывод

| Profile | S4 | S6 |
|---|---|---|
| Исходный baseline, user confirmed | Technical PASS / semantic FAIL: weather-rule и неверные выводы; 8.065 s HTTP, 661 output tokens, warm | Technical PASS / semantic PARTIAL: копия кода, lifecycle не объяснён; 9.028 s, 730 tokens, warm |
| explain-evidence-v1, user accepted | Technical FAIL length=2048, 26.361 s, cold load 2.364 s; зацикливание, practical improvement не подтверждено | NOT RUN по gate |
| compact-evidence-v1, assistant provisional | Technical PASS / semantic PASS по основной задаче; 4.898 s, 202 tokens, cold load 2.324 s | Technical PASS / semantic FAIL; 9.970 s, 860 tokens, warm |

Compact S4 существенно короче и корректнее по scope; compact S6 не стал практически надёжным объяснением Compose. S6 оказался длиннее/медленнее исходного ответа и добавил смысловую ошибку. Это единичные прогоны с разным load/cache state и совместным изменением schema/instruction; причинное утверждение об эффекте только schema или устойчивом ускорении невозможно.

**Практический итог:** гипотеза упрощения формата получила ограниченную поддержку в S4 (нет нерелевантного применения, краткое объяснение, завершённый ответ), но достаточная полезность Kotlin/Compose Assistant не подтверждена. Technical 2/2 PASS не закрывает смысловой FAIL. В default CLI профиль не переносится; новые эксперименты не предлагаются как автоматическое продолжение.

## Остановка

Новых attempts 2, оба завершены; новый bounded client wall 15.626323 s. Общая история **14/32 attempts, 220.800325 / 5400 s** записанного bounded client wall. Read-only preflight выполнялся отдельно, не включён в эту метрику. Исторические отказы входят в знаменатель, journal не обнулил общий бюджет.

Task 7.3: запуски и assistant review завершены, joint user review pending, checkbox пока открыт. OpenSpec **22/33**. Код не менялся; принятые **349 passed / 1 skipped** — предыдущая offline-проверка, повторно не запускалась. После документации выполнена strict validation. RAG/оптимизации/другие модели не запускались. Commit/push, archive и видео не выполнялись. Остановлено для совместного review.
