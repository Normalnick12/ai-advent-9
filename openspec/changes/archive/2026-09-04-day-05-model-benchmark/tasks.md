## 1. Canonical benchmark and deterministic verifier

- [x] 1.1 Перенести canonical prompt, instructions, strict schema и общие request fields из design в новый backend domain; проверить fingerprint `01914c54838704723619457331e4d787299a23d010fdb23b1e66f725947d755c`, required/additionalProperties и отсутствие эталонов/model-specific данных в отправляемом payload.
- [x] 1.2 Реализовать независимые arithmetic/permutations/subsets verifier для Task 1–3; проверить 468, единственное расписание, optimum A+C+F+G с cost 15/value 29 и отрицательные кейсы повторов, неизвестных фич, нарушения каждого ограничения, неверных totals и независимости от порядка фич.
- [x] 1.3 Реализовать Task 4 прямыми in-place циклами и Task 5 полным перебором 3^10; проверить final_array `[22, 15, -10, -10, 11, 18, -28, -12]`, checksum -147, count 24, границы последних B, ровно две соседние AB и неправильный checksum при правильном массиве.
- [x] 1.4 Добавить строгий разбор model output и verdict/quality aggregation; тестами подтвердить 5/5 и 4/5 для count 21, реальный 0/5 completed ответа, nullable quality/unverified при incomplete/refusal/invalid shape, bool/string вместо integer и отсутствие partial JSON repair.

## 2. Model registry and actual-usage pricing

- [x] 2.1 Создать единый backend allowlist/role defaults/совместимые resolved mappings и versioned rate registry Luna/Terra/Sol; перепроверить официальные цены при apply, записать source URL/checked_at/service tier и тестами проверить полноту registry, defaults и невозможность публикации некорректной конфигурации.
- [x] 2.2 Реализовать Decimal cost по input/cached/cache-write/output usage без повторной оплаты reasoning; тестами проверить пример 0.000769 USD из specs, реальные usage третьего probe, incomplete с известной стоимостью, неизвестные counters/resolved id/tier, противоречивые counts и отсутствие расчёта от лимита 6000.

## 3. Backend transport contracts and catalog

- [x] 3.1 Добавить отдельные strict request/response DTO для catalog, трёх role selections, config snapshot, task verdict/actual/reference, normalized/raw status, nullable usage и decimal-string cost; проверить serialization, запрет extra fields, ровно три роли и отсутствие API-key field.
- [x] 3.2 Добавить `GET /api/v1/model-benchmark/catalog` с backend defaults и разрешёнными ids для каждой роли; API tests должны подтвердить отсутствие OpenAI calls/зависимости от ключа, read-only config и отсутствие произвольных ids.
- [x] 3.3 Подготовить предварительную валидацию run selections и rate configuration; API tests должны подтвердить 422 для missing/unknown/extra полей, отказ до upstream calls при некорректной конфигурации и допустимость одинаковой модели в нескольких слотах без дедупликации.

## 4. Responses API execution and batch endpoint

- [x] 4.1 Добавить единый request builder и fresh одинаково настроенный клиент на слот с medium/6000/default tier, store false, omitted temperature/top_p, `max_retries=0`; mocked SDK tests должны сравнивать все kwargs кроме model и подтверждать ровно один call со всеми задачами, без дополнительных tools/cache/reasoning параметров или fallback.
- [x] 4.2 Реализовать per-slot monotonic latency, API call count, HTTP timeout 240 s/connect 15 s и wall-clock bound 240 s; тестами проверить completed, incomplete с reason и usage, refusal, malformed output, API error, timeout, null resolved/usage без ответа и сохранение доступных метрик без unsafe exception dumps.
- [x] 4.3 Реализовать конкурентный запуск трёх слотов с изоляцией ошибок и стабильным role order; concurrency/failure tests должны подтвердить, что один failure не отменяет два результата, timeout не вызывает повтор, а API call count отражает 0 до/1 после начала попытки.
- [x] 4.4 Подключить dependency-injected `POST /api/v1/model-benchmark/run` в main.py с request id, config snapshot, тремя результатами и безопасными logs; API tests должны проверить mixed batch, per-task references только для incorrect, cost независимо от quality и неизменность контрактов существующих трёх endpoints.

## 5. Android data and session state

- [x] 5.1 Добавить kotlinx.serialization DTO, Retrofit catalog/run API и repository, передающие только три selections; JVM tests должны проверить exact payload, nullable quality/usage, decimal-string cost и сохранение model ids/status/raw answers.
- [x] 5.2 Подключить repository через AppContainer с отдельным клиентом (connect 10 s, write 30 s, read 260 s, call 300 s, retryOnConnectionFailure false); transport tests должны подтвердить новый бюджет и неизменность существующего клиента Day 02–04.
- [x] 5.3 Добавить Activity-scoped constructor-injected ViewModel с загрузкой каталога при первом посещении, явным повтором каталога, defaults и selections; tests должны подтвердить отсутствие запроса при одном создании ViewModel, отсутствие локального allowlist fallback и независимость от состояния других дней.
- [x] 5.4 Реализовать один run на tap, loading lock, snapshot выбранных моделей, последний batch и отдельный run error; coroutine tests должны проверить duplicate taps, отсутствие повторов после ошибок/navigation/rotation, сохранение предыдущего результата при transport error и неизменность старых карточек после смены selectors.

## 6. Russian UI and learning-days integration

- [x] 6.1 Добавить Day 05 в MainActivity/AppRoot/LearningDaysHome с заголовком «Лаборатория моделей», описанием сравнения и «Назад к дням»; обновить root navigation tests для четырёх карточек 02–05, toolbar/system back, доступности без backend и отсутствия автозапуска benchmark.
- [x] 6.2 Реализовать три role selectors из каталога, индикацию повторяющейся модели, «Запустить сравнение», loading/error и read-only «Параметры эксперимента» со всеми задачами и пояснением «Меняется только модель»; Compose tests должны проверить русские подписи, блокировку controls и отсутствие editable prompt/settings/playground.
- [x] 6.3 Реализовать три компактные карточки с quality/time/total tokens/cost/status; UI tests должны отличать unverified от реальных 0/5, сохранять две успешные карточки при сбое третьей, отображать unknown как «Нет данных» и малую известную стоимость как ненулевую.
- [x] 6.4 Добавить раскрываемые Task 1–5 с actual/verdict/reference для ошибки, raw output и detailed usage/model/status/API calls/pricing formula/source/date; fake-result UI tests должны проверить 21 против 24, отсутствие придуманного ответа у incomplete и отсутствие двойного подсчёта reasoning в подписи токенов.
- [x] 6.5 Сохранить session selections/results/running state через переходы и rotation, scroll/expansion по request_id; проверить соответствующие ViewModel/Compose сценарии и визуально узкий экран с увеличенным шрифтом без обрезки, перекрытия системными панелями и обязательной горизонтальной прокрутки.

## 7. Documentation and integrated verification

- [x] 7.1 Создать во время apply краткий `day-05-model-benchmark/README.md`: назначение, зависимости, ссылки на setup, `OPENAI_API_KEY` только в backend, запуск, fixed experiment, три исторических probes и их ограниченность, учебный вывод о выборе по use case; обновить необходимые root/backend/Android ссылки и проверить отсутствие секретов и implementation dump в Day README.
- [x] 7.2 После завершения кода выполнить backend suite (`.venv/Scripts/python.exe -m pytest` из каталога backend) и Android unit/build из корня через PowerShell 7 `scripts/dev.ps1 unit` и `scripts/dev.ps1 build`; убедиться, что проверки новых контрактов и регрессии Day 02–04 проходят без live API dependency.
- [x] 7.3 После всех связанных UI/navigation изменений выполнить полный `scripts/dev.ps1 ui` через PowerShell 7 на переиспользованном эмуляторе; подтвердить root navigation/session regression и новые fake-backend UI states, не повторяя успешно пройденные проверки без изменения входов.
- [x] 7.4 Отдельно от offline checks запустить/переиспользовать backend в управляемой терминальной сессии через `scripts/dev.ps1 backend`, проверить `status` и доступ backend с эмулятора, затем выполнить один явный E2E benchmark через UI; проверить три слота, настройки, calls/status, actual/verifier answers и usage-based cost. Не требовать воспроизведения 4/5/5 и не делать дополнительные paid probes ради исторического результата; безопасно записать фактический outcome.
- [x] 7.5 Выполнить `openspec validate day-05-model-benchmark --strict`, проверить синтаксис/структуру изменённых файлов и `git diff`/`git status` на scope и отсутствие secrets/локальных артефактов; передать пользователю результат для проверки, без автоматического commit/push или archive.
