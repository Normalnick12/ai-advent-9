## 1. Проверка внешнего контракта и фиксация конфигурации

- [x] 1.1 Проверить SDK input-token count signature, model/snapshot, Standard rates и cache-write semantics по официальным источникам design; завершение проверить зафиксированным config/pricing record с датой/ссылкой без изменения Day 05 и без tiktoken.
- [x] 1.2 После review выполнить отдельный opt-in smoke нового provider contract: current-only single user без instructions; non-empty history-only user/assistant fixture без instructions; exact full instructions+history+current; deterministic oversized full с integer 132000–160000. Все четыре обязательных measurements должны вернуть nonnegative integer; проверить generation=0/commit=0. Сохранить безопасные результаты в существующем provider-count-smoke.md, не переписывая прежний failure; при любом отказе/malformed/bounds failure остановить apply для review без fallback.

## 2. Нейтральные модели и изоляция Agent

- [x] 2.1 Добавить frozen config injection с прежними Day 06/07 defaults и fixed Day 08 configuration, нейтральные TokenUsage/TokenDiagnostics/AgentTurnResult; проверить unit fixtures и прежний exact Day 06/07 generation payload/HTTP projection.
- [x] 2.2 Сохранить actual nullable counters, resolved model и requested/actual tier в LLM adapter для completed и non-completed outcomes; проверить malformed/missing/zero values и отсутствие потери usage в invalid-completed ветке.
- [x] 2.3 Создать Day 08 instance того же SimpleAgent, отдельный manager и SQLite-файл config-version namespace с прежней schema; проверить reopen, отсутствие migration старой базы, раздельные paths и cleanup при partial startup failure.
- [x] 2.4 Добавить Day 08 create/GET/delete namespace и строгую маршрутизацию без global lookup; проверить wrong-namespace get/send/prepare/execute=404, harmless cross-delete и изоляцию после restart без OpenAI calls для metadata lifecycle.

## 3. Provider preflight и обычный turn

- [x] 3.1 Реализовать маленький async TokenCounter/OpenAI adapter с явным include_instructions и общий full context payload helper; проверить exact Unicode/roles/text/order одного snapshot, omission instructions в standalone current/history, соответствие full count generation и отсутствие unsupported reasoning/generation-only kwargs у count.
- [x] 3.2 Реализовать независимые current_message_tokens, saved_history_tokens и preflight_input_tokens без cache framework и разностной атрибуции. Проверить structural history=0 без API при пустой history, независимую integer validation (включая bool/negative/missing), fixture current=12/history=31/full=40 без sum/order check, отсутствие synthetic/dummy inputs и count calls в Day 06/07/metadata lifecycle.
- [x] 3.3 Интегрировать counts в обычный Day 08 Send под session guard без mandatory preview: current-only -> history-only либо structural zero -> full. Проверить 2 count calls первого turn, 3 при непустой history, максимум одну generation; preflight_input_tokens>128000 rejection и reserve warning только от exact full. На failure любой стадии сохранить частичные diagnostics, не выполнять оставшиеся calls/generation/commit, не менять history.
- [x] 3.4 Добавить bounded count/generation deadlines и safe failure mapping; проверить освобождение busy при timeout/cancel, 409 конкурирующей session operation и прогресс независимой session.
- [x] 3.5 Добавить Day 08 message/result DTO и endpoint с только message до 20000 символов; проверить snapshot metrics до commit, count после commit, diagnostics на failed outcomes и отсутствие history/config/raw SDK в wire/logs.

## 4. Pricing текущей попытки

- [x] 4.1 Реализовать отдельный Day 08 Decimal calculator с allowlist alias/snapshot, fixed default-tier rates/date/source; проверить fixture I=1000,C=200,O=100 -> USD 0.000195, без повторного reasoning billing.
- [x] 4.2 Обработать optional cache-write как обычный input без надбавки, не подменяя missing W нулём; проверить known W, C+W>I, C>I, R>O, inconsistent total, unknown model/tier и missing mandatory counters -> unavailable.
- [x] 4.3 Присоединить estimated cost к Day 08 outcomes независимо от commit; проверить incomplete/refusal с usage, отсутствующий usage и completed с unavailable cost, сохранив прежние Day 05 pricing tests/results без рефакторинга.

## 5. Контролируемый overflow workflow

- [x] 5.1 Реализовать deterministic recipe v1 и bounded prepare поверх actual saved history: только full count, максимум четыре probes, accepted preflight_input_tokens 132000–160000, serialized payload до 2 MiB и общий deadline. Проверить детерминированную коррекцию N по measured full, новый exact count каждого кандидата без смешивания diagnostics, отсутствие standalone current/history calls, safe bounds/count failures и generation=0/commit=0.
- [x] 5.2 Добавить preparation DTO с recipe/sample, repetitions, chars/bytes/full payload bytes, digest, exact full metrics и предупреждением; standalone current/history not_measured/null (empty history structural 0). Проверить отсутствие internal history в ответе и совпадение digest/count с exact prepared generation payload.
- [x] 5.3 Добавить runtime-only одноразовые preparation IDs с TTL 10 минут, одним active ID на session, cap 16 и invalidation при normal commit/reset/restart; проверить stale/mismatched/expired/used ID, отсутствие busy во время ожидания пользователя и отсутствие durable preparation state.
- [x] 5.4 Реализовать execute с confirm=true, атомарным потреблением разрешения до await и ровно одной generation через общие SimpleAgent helpers; проверить double-click/concurrent/repeated execute, zero retries, неизменный snapshot и отсутствие commit path даже при unexpected provider acceptance.
- [x] 5.5 Нормализовать только allowlisted structured provider context errors как context_limit_exceeded; проверить 400 без context code, 413, 429, timeout, count-endpoint rejection и unexpected acceptance как отдельные outcomes, с сохранёнными diagnostics/usage.
- [x] 5.6 Проверить интеграционно на реальном временном SQLite-файле сохранность пар после preflight/probe failures, storage reopen и следующий normal success ровно +1 pair; подтвердить, что oversized payload ни разу не записывается.

## 6. Android лаборатория и отображение

- [x] 6.1 Добавить TokenLab API/Repository DTO, отдельный TokenLabViewModel и AppContainer dependencies с Day 08 ID preferences; проверить serialization, restore/save-before-send/reset ordering и отсутствие history/config в requests.
- [x] 6.2 Минимально выделить stateless chat components и собрать отдельный экран normal Send/diagnostics; проверить прежние ChatViewModel/ChatScreen JVM/UI tests и новый Send без Preview с draft preservation на ошибке.
- [x] 6.3 Показать standalone current/history, exact full preflight, actual I/O, context preflight_input/128000 и estimated cost с details. Явно объяснить неаддитивность; не выводить системную карточку/разность. Проверить mock UI differing counts, fixture 12/31/40, empty-history zero versus unavailable/not_measured, >100%, before-commit snapshot и маленькие USD без ложного $0.00.
- [x] 6.4 Добавить runtime-only таблицу последних 20 attempt IDs с outcome/actual I/O/cost; проверить deduplication, отличие attempt number от committed count, navigation retention и отсутствие восстановления metrics после process restart/reset.
- [x] 6.5 Добавить явные prepare/execute/cancel controls и предупреждение с recipe/размером; проверить, что prepare/open/navigation не генерируют, execute доступен только для подтверждённой актуальной подготовки, а repeated click не отправляет второй request.
- [x] 6.6 Реализовать recovery для known context rejection, stale preparation, unknown normal send и unknown execute; проверить нормальное продолжение после подтверждённого overflow, metadata refresh после unknown probe и отсутствие автоматического replay/model switching.
- [x] 6.7 Добавить видимый редактируемый long fixture на 200 строк в пределах 20000 символов, карточку 08, destination/title и независимое сохранение состояния; проверить fixture length, отсутствие auto-send и navigation tests всех Day 02–08.

## 7. Regression и живой acceptance

- [x] 7.1 Выполнить backend pytest по проектной инструкции, включая прежние Day 02–07 tests и новые counter/Agent/API/SQLite/pricing/probe tests; проверить синтаксис изменённых Python файлов и отсутствие секретов/локальных данных в diff.
- [x] 7.2 Выполнить Android JVM tests и build через PowerShell 7 scripts/dev.ps1; выполнить затронутые TokenLab/chat UI tests и связанный navigation regression, при связанных изменениях экранов — полный UI-прогон через тот же скрипт. Проверить читаемость с IME/большим шрифтом; повторять только проверки изменённых inputs или диагностируемых рисков.
- [x] 7.3 Подготовить backend в управляемой сессии и эмулятор через scripts/dev.ps1, проверить status и доступ backend из эмулятора отдельно от OpenAI; пройти четыре actual short/short/long/short turns из design и зафиксировать реальные counts/cost без предзаданных ожидаемых чисел.
- [x] 7.4 После видимой успешной oversized preparation выполнить один явно подтверждённый пользователем probe в UI; завершение подтвердить actual generation context-limit rejection, preflight_input_tokens в диапазоне 132000–160000, неизменным count/history после reopen и следующим short normal turn/count +1. При 413/429/count rejection/timeout или отсутствии live запуска оставить эту задачу открытой, не заменять mock/soft limit/fallback model.

## 8. Документация и завершение apply

- [x] 8.1 Создать day-08-token-lab/README.md по краткому Day шаблону с проверенными результатами либо явной отметкой непроведённой проверки; объяснить standalone current/history против exact full и их неаддитивность без вычисления системной части, full-history линейный context/квадратичный cumulative input, будущую цену assistant output, cache effects и видимый deterministic overflow recipe без выдуманных измерений.
- [x] 8.2 Обновить только необходимые backend/Android/scripts README по namespace/database/запуску и проверкам; проверить ссылки, отсутствие duplication установки в Day README, неизменность Day 05 historical results и отсутствие persistent metrics schema.
- [x] 8.3 Проверить согласованность реализации и всех scenario contracts, выполнить strict validate change и current specs, git diff --check/status; оставить live acceptance checkbox открытым до фактического подтверждения, не выполнять archive/commit/push без отдельного запроса пользователя.

Исторический baseline HTTP 400, transient timeout и последующие успешные independent-count smoke сохранены хронологически в [provider-count-smoke.md](provider-count-smoke.md). Tasks 1.1–1.2 завершены. Результаты реализации, offline/integration проверок и подтверждённого пользователем live acceptance — в [verification.md](verification.md). Tasks 7.3–7.4 завершены по ручному short/long/overflow/recovery прогону; всего 34/34. При фиксации этих результатов дополнительные provider calls не выполнялись.
