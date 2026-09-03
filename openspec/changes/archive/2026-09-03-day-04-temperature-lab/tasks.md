## 1. Live OpenAI compatibility gate

- [x] 1.1 До любых production-изменений выполнить с локальным `OPENAI_API_KEY` живой Responses API probe точного canonical benchmark и planned strict schema на `gpt-5.6` при `reasoning.effort=none`, standard mode, `max_output_tokens=600`, default/omitted `top_p` и temperature 0/0.7/1.2; проверить, что все три вызова приняты и разобраны, их envelopes отличаются только temperature, а sanitized результат сохранён для будущего README. Если ключ отсутствует или хотя бы одна комбинация несовместима, остановить apply, сообщить точную безопасную диагностику и обновить planning artifacts после решения пользователя, не применяя fallback. Probe: SDK 2.54.0; все три status `completed`; resolved model `gpt-5.6-sol`; strict shape parsed; latency 5580/2995/3374 ms; total tokens 327/341/326; `top_p` omitted и envelopes равны кроме temperature.

## 2. Backend benchmark domain and contracts

- [x] 2.1 Добавить единственную backend-константу canonical prompt и точное определение `benchmark`/`free` mode без нормализации input; проверить unit tests на полное совпадение, односивольную/whitespace правку и неизменность переданной строки.
- [x] 2.2 Реализовать pure validator пяти формальных критериев, whitespace/casefold normalization и Unicode standalone forbidden-word tokenization; проверить unit tests на ровно/не ровно пять вариантов, 1–2 слова, normalized duplicates, все регистры `Interview`/`AI`/`ИИ`, punctuation boundaries, более длинные tokens и слоганы на границе 8/9 слов.
- [x] 2.3 Добавить строгие Pydantic request/response модели для experiment config, mode, temperature result, usage, variants с backend-computed normalized names, пяти validation checks и safe errors; проверить model tests на запрет extra fields, nullable validation для непроверенных ответов и стабильную serialization трёх результатов.

## 3. OpenAI temperature execution

- [x] 3.1 Добавить общий request-envelope builder для `gpt-5.6`, none/standard reasoning, 600 tokens, disabled storage/implicit cache, zero retries и mode-specific output contract; проверить mocked SDK tests, что три kwargs после удаления temperature полностью равны, `top_p`/instructions/tools отсутствуют, benchmark schema strict и не содержит `minItems`, `maxItems` или `uniqueItems`, а free mode использует обычный text format.
- [x] 3.2 Реализовать один per-temperature вызов с monotonic latency, completed/incomplete/parse/timeout/bad-request/upstream normalization, full token breakdown и безопасной redaction; проверить tests на parsed benchmark/text content, доступный usage, nullable validation при сбое и отсутствие prompt/API key в response и logs.
- [x] 3.3 Реализовать конкурентный запуск temperature 0/0.7/1.2 с `gather(return_exceptions=True)` и стабильным result order; проверить concurrency test на одновременные calls, отдельные latency и сохранение двух успешных результатов при одном failure без hidden retry или изменённой конфигурации.

## 4. FastAPI integration

- [x] 4.1 Добавить dependency-injected `POST /api/v1/temperature-lab/run`, request id и безопасное batch/per-temperature logging, не меняя `/api/v1/generate` и `/api/v1/reasoning-lab/run`; проверить API tests для benchmark, free mode, invalid empty prompt и partial failure, а также regression tests обоих существующих endpoints.
- [x] 4.2 Проверить API contract assertions на read-only config (`gpt-5.6`, temperatures, none/standard reasoning, 600, default top_p, output mode), exact prompt forwarding, «N/5» data только после benchmark validation и явное free-mode сообщение без creativity/accuracy fields.

## 5. Android data and session state

- [x] 5.1 Добавить kotlinx.serialization DTO, Retrofit API/repository и `AppContainer` wiring для одного Temperature Lab batch request; проверить serialization/repository tests на точный prompt, три temperature results, nullable benchmark fields, normalized names и отсутствие любого API-key field.
- [x] 5.2 Добавить constructor-injected Temperature Lab ViewModel с canonical default prompt, edit/restore actions, empty-input error, loading lock и latest/partial/error state; проверить coroutine tests на один request на tap, неизменный prompt, блокировку duplicate launch, «Вернуть benchmark» и сохранение частичных результатов.
- [x] 5.3 Реализовать active history bucket максимум из трёх newest-first batches одного точного prompt только в памяти; проверить tests на eviction четвёртого run, скрытие истории при редактировании, замену scope после batch другого prompt, сохранение при transport failure и пустое состояние нового ViewModel.
- [x] 5.4 Реализовать отдельные session-long benchmark accumulators `normalized unique / total generated` по каждой temperature из backend normalized names; проверить tests на normalized duplicate, независимость temperature, учёт результатов старше history limit и отсутствие изменений/отображения в free mode.

## 6. Android Material 3 UI

- [x] 6.1 Добавить третью destination «Лаборатория температуры» в существующую root navigation без нового module/dependency; проверить Compose test или emulator smoke, что экраны Day 02, Day 03 и Day 04 доступны и существующие navigation behavior/tests не сломаны.
- [x] 6.2 Построить русскоязычный экран с многострочным editable prompt, «Запустить сравнение», «Вернуть benchmark» и expandable read-only «Параметры эксперимента» с пояснением «Меняется только temperature»; проверить phone-size UI, что controls читаемы, fixed settings не редактируются и prompt восстанавливается точно.
- [x] 6.3 Добавить три result cards temperature 0/0.7/1.2 со status, tokens, отдельной latency, benchmark-подписью «Соблюдение требований: N/5» или free-mode сообщением и expandable selectable ответом; проверить UI states для benchmark, free mode, incomplete и partial failure без автоматического ранжирования latency.
- [x] 6.4 Отобразить максимум три history runs текущего prompt и benchmark-only секцию «Уникальные названия» с отдельным `unique / total` для каждой temperature; проверить Compose/ViewModel integration, что история разных prompt не смешивается, free mode скрывает aggregates и весь текст нового экрана пользовательски русскоязычный.

## 7. Documentation and verification

- [x] 7.1 Создать `day-04-temperature-lab/README.md` как точку входа с целью, fixed/default параметрами, canonical/free modes, пятью formal checks, оговорками о creativity/latency, архитектурой, зависимостями, настройкой `OPENAI_API_KEY`, запуском backend/app, sanitized live-probe outcome и командами проверок; обновить необходимые root/backend/Android README links и проверить отсутствие реальных secrets.
- [x] 7.2 Запустить полный backend test suite и проверить, что новые и существующие tests проходят без live OpenAI dependency после завершённого compatibility gate.
- [x] 7.3 Запустить Android unit tests и `assembleDebug` и проверить успешную сборку единственного `app` module без новых warnings/errors, связанных с Day 04.
- [x] 7.4 С локальным `OPENAI_API_KEY` выполнить end-to-end backend/Android emulator smoke для canonical benchmark и изменённого prompt; проверить три карточки, exact config, N/5 только в benchmark, free text notice, expand/collapse, history limit, unique counters и сохранение экранов Day 02/03.
- [x] 7.5 Просмотреть `git diff`/`git status`, проверить отсутствие secrets, `.env`, virtualenv/cache/build/IDE artifacts и непреднамеренных изменений Day 01–03; оставить commit/push до отдельного явного запроса на завершение Day 04.
