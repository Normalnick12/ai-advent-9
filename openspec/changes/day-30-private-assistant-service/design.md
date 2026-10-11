## Context

См. [proposal.md](proposal.md), раздел Why. Runtime находится в `day-27-local-architecture-assistant/`: `rag_cli.main` собирает сценарий, отдельные модули отвечают за Workspace, Knowledge, retrieval, payload, validation и Ollama transport. Day 28 использует этот runtime, Day 29 содержит отдельный экспериментальный driver. Его compact/prompt варианты не приняты в default CLI. Исторические результаты и незавершённые проверки Days 27–29 сохраняются.

Windows-ПК с RTX 4070 SUPER 12 GB и 32 GB RAM — единственная обязательная серверная платформа приёмки. Mac M1 — будущая проверка переносимости. Исходный backend прежних недель создаёт OpenAI-клиенты и хранилища в lifespan, поэтому его приложение не импортируется. Новая capability не требует изменения main specs прежних дней.

Design обязателен из-за новой сетевой границы, optional dependencies, конкурентного исполнения и обработки недоверенной истории.

## Goals / Non-Goals

**Goals:** единый сценарий объяснения для CLI/HTTP; добровольное включение сервиса; ограниченный stateless chat; минимальная установка и остановка; защищённая демонстрация двух клиентов; явные технические результаты без переоценки модели.

**Non-Goals:** OS sandbox против враждебного локального процесса; multi-tenant isolation; выполнение предложенного моделью кода; чтение произвольного файла; автоматическое управление Ollama, моделями, индексом или Tailscale; гарантированная отмена GPU-job; полноценный чат-продукт или новый benchmark. Границы функциональности перечислены в proposal.

## Decisions

### 1. Optional adapter and one shared runtime

В `day-30-private-assistant-service/` размещаются небольшое FastAPI-приложение, отдельно устанавливаемые HTTP-зависимости, интерактивный Python-клиент, focused tests и README. Общие функции остаются в существующей утилите. Из `rag_cli.main` выделяется одна операция, возвращающая структурированные result/sources/metrics без print, argparse, stdin и transcript writer. CLI сохраняет свои parser, rendering, exit codes и stderr metrics. HTTP вызывает ту же операцию, а не CLI subprocess и не копию RAG.

Новые аргументы общей операции для истории и сетевых deadline/error categories имеют обратно совместимые defaults. При отсутствии истории прежние prompt/schema/wire settings остаются прежними; HTTP не включает Day 29 compact или prompt corrections. Core не импортирует FastAPI/Pydantic/Uvicorn. HTTP requirements подключают существующие core requirements, а не наоборот. Чистое CLI-окружение без HTTP-пакетов проверяется отдельно.

Сервис запускается вручную, одним Uvicorn worker, без reload/autostart, default `127.0.0.1:8030`; штатный launcher Day 30 разрешает только этот loopback bind. Ollama URL — серверная настройка только `http://127.0.0.1:<port>` с default 11434, без credentials/path/query/redirect/proxy. Более широкий существующий CLI loopback validator не расширяется для HTTP и его совместимость не меняется. Запуск HTTP не запускает/перезапускает Ollama и не открывает firewall/router ports.

Альтернативы: Starlette уменьшает framework surface, но требует ручной валидации; Flask не упрощает контракт; stdlib HTTP требует лишней защитной логики. Существующий FastAPI backend тянет несвязанные сервисы. FastAPI используется только как адаптер.

### 2. Server-owned sources and a small profile

Локальная конфигурация вне Git задаёт Workspace, отдельную Knowledge и явное соответствие `file_id -> relative .kt`. Все разрешённые клиенты принадлежат одной доверенной группе и имеют одинаковый доступ к этому synthetic corpus. ID ограничивается ASCII `[a-z0-9_-]{1,64}`; клиент не управляет путями, моделью, URL, retrieval или prompt. Неизвестный ID возвращает 404. Конфигурация проверяется до запуска обслуживания, выбранный файл читается безопасным reader при каждом ходе. Allowlist ID не заменяет проверку confinement, symlink/junction/reparse points, UTF-8 и размера.

Knowledge подключается и индексируется владельцем прежним CLI. Обслуживание читает SQLite в read-only режиме и проверяет freshness/provenance; на stale/corrupt index — 503 без rebuild/fallback. Workspace и Knowledge остаются раздельными. Параллельная административная переиндексация во время демонстрации исключается; конкурентная смена index должна давать существующий контролируемый отказ, а не смешанный snapshot.

Начальный HTTP-профиль: `qwen2.5-coder:7b-instruct-q4_K_M`, зафиксированный при подготовке digest, `num_ctx=8192`, `num_predict=2048`, temperature 0, seed 28, keep_alive `5m`, think false при поддержке. Это технический кандидат. Передача профиля клиентом запрещена, автоматической смены/скачивания модели нет. Metadata проверяет локальность и ожидаемый digest. Эксплуатационная проверка local-only включает отключение Ollama cloud features; loopback сам по себе не доказывает локальность модели.

HTTP baseline использует существующий FTS5 text retrieval, top_k 4. Он переиспользует Knowledge/RAG без query embeddings и переключений модели. Vector и none остаются в CLI; их сетевые переключатели не нужны для Day 30. Детерминированный query состоит из текущего вопроса, последнего user-вопроса history (если есть), затем имени выбранного Kotlin-файла/CamelCase terms. Старые assistant-ответы не участвуют в retrieval. Каждый пользовательский вопрос ограничен 2000 символами; enriched query — 4096 символами и 64 уникальными literal terms. Превышение даёт 422 до inference, без скрытого обрезания и LLM rewrite. Offline fixture проверяет настоящее уточнение «А когда это разрешено?»: нужное правило находится по последнему user-вопросу, но не по одному текущему вопросу/нейтральному имени файла.

### 3. Client-owned conversation, current evidence

Контракт `POST /v1/chat`:

```json
{
  "file_id": "checkout-demo",
  "question": "Почему переход выполняется после оплаты?",
  "history": [
    {"user": "Какова роль этого класса?", "assistant": "Предыдущий ответ для уточнения"}
  ]
}
```

`history` optional, default `[]`, от старой пары к новой. Максимум две полные пары с ровно двумя непустыми строками `user`/`assistant`. Бюджет истории — длина UTF-8 JSON массива, сериализованного с `ensure_ascii=False` и compact separators, максимум 8192 bytes, включая структуру. Invalid Unicode, неполные пары, дополнительные поля и произвольные system/tool/role messages дают 422 до обращения к данным и Ollama. История не подписывается и считается полностью клиентским недоверенным вводом.

В payload история добавляется отдельным полем данных рядом с вопросом; клиентские строки никогда не становятся system/tool instructions. Дополнительная инструкция применяется только к HTTP chat: прошлые ответы могут быть неверны, нужны текущие Kotlin/Markdown evidence; при нехватке данных назвать ограничение. Validation использует только текущие line count и selected chunks: ссылки/цитаты из одной лишь истории не принимаются. Prompt — помощь в поведении, реальные границы файлов/прав/ресурсов обеспечиваются кодом.

Минимальный интерактивный клиент хранит последние пары в RAM, читает вопросы через stdin и выводит проверенный ответ через существующий безопасный renderer. Token берётся из окружения/локального секретного файла, не аргумента shell и не URL. Нет transcript-файла. Смена file_id или явный reset очищают историю; при новом ходе клиент удаляет только целые старейшие пары до лимита и сообщает об этом. Если даже последняя пара слишком велика, клиент явно сообщает о сбросе контекста, не режет цитату посередине. Ошибочные ответы не добавляются в историю. После закрытия клиента история теряется. Сервер не пишет вопросы/ответы и не создаёт session IDs/таблицы.

### 4. HTTP surface and safe outcomes

| Route | Auth | Meaning |
|---|---|---|
| GET /healthz | Нет, только минимальное `{"status":"ok"}` | Event loop/process жив; без файлов/Ollama |
| GET /readyz | Bearer | 200 prerequisites ready, 503 not ready; не generation test |
| GET /v1/status | Bearer | ready/degraded, active/limit, публичный ID профиля и лимиты |
| POST /v1/chat | Bearer | Один ограниченный ход, без streaming |

Readiness проверяет локальную конфигурацию, доступность разрешённых источников/индекса и metadata установленной модели без inference/load/embed/pull. Metadata I/O имеет общий бюджет 5 s; readiness можно кешировать до 5 s, при новом известном сбое кеш инвалидируется. Каждый chat всё равно заново проверяет данные. Capacity saturation не означает неисправность зависимостей: ready может оставаться true при active=2, но новый chat получит 503. Startup/readiness не делают warm-up. `/api/ps` не доказывает свободный runner или отсутствие активного inference.

200 chat response содержит server-generated request_id, существующий structured result (observations/rules/applications/assumptions/limitations/knowledge_status), source descriptors только выбранных chunks (ID, разрешённое relative name, section, lines), `mechanical_validation: passed`, `semantic_status: not_evaluated`, ограниченные usage/timing metrics. Source descriptors формирует приложение; raw Ollama response, reasoning, полный corpus и абсолютные пути не возвращаются. Полный Kotlin не эхо-полем; сам текст ответа может цитировать разрешённые данные. `Cache-Control: no-store` устанавливается на chat/status/error responses.

| Status | Stable error code / condition |
|---|---|
| 401 | unauthenticated: отсутствующий/неверный token |
| 404 | file_not_found: неизвестный или недоступный ID |
| 413 | request_too_large: raw HTTP body |
| 415 | unsupported_media_type: не JSON или сжатое тело |
| 422 | invalid_request / context_budget_exceeded: schema, история, вопрос, данные не помещаются |
| 429 | rate_limited + Retry-After |
| 503 | capacity_exceeded / upstream_unavailable / upstream_overloaded / knowledge_unavailable / recovery_required |
| 504 | request_timeout / body_timeout |
| 502 | invalid_model_response: незавершённый/невалидный ответ модели |
| 500 | internal_error: безопасный неизвестный сбой |

Ошибка содержит только фиксированный code/message и request_id; без `str(exception)`, validation input, traceback и upstream body. Typed error categories добавляются обратно совместимо к core, вместо разбора русских сообщений по substring. Ответ модели с `done_reason=length` не выдаётся частично как успех. Нет repair/retry.

### 5. Authentication, limits and privacy

Локально настроенные случайные Bearer-токены на устройства, минимум 32 случайных bytes, сравнение constant-time; отсутствие конфигурации token запрещает старт. TLS не требуется только для локального loopback; удалённый доступ — HTTPS через приватный transport. Все маршруты кроме минимального health защищены. Auth и допуск по rate выполняются до чтения Workspace/Knowledge/Ollama; body cap действует на входной поток до полного JSON parsing. CORS по умолчанию закрыт, встроенные docs/OpenAPI endpoints выключены; browser UI не входит в scope.

| Limit | Initial contract |
|---|---|
| Raw HTTP JSON body | 32 KiB; счёт реально полученных bytes, также без Content-Length/chunked |
| Body receive deadline | 10 s; compressed body запрещён |
| Current question | Непустая строка, максимум 2000 Unicode code points |
| History | До 2 пар и 8 KiB по правилу выше |
| File | До 16 KiB; прежний reader |
| Whole Ollama chat JSON | До 24 KiB, включая историю, schema, инструкции, Kotlin и selected chunks |
| Model context / output | 8192 / 2048 tokens, клиент не переопределяет |
| Upstream response | До 256 KiB; metadata до существующего лимита 2 MiB |
| Chat rate | Token bucket per authenticated token: refill 6/min, capacity 2, monotonic clock |
| Authenticated ready/status rate | Общий отдельный bucket 30/min, capacity 5 на token |
| Chat admission | 2, без application waiting queue |
| Uvicorn protective concurrency | 32 connections/tasks; не substitute chat admission |

32 KiB ingress позволяет историю плюс Unicode/JSON escaping, но внутренний 24 KiB бюджет независим и может отклонить такой запрос. История сначала резервируется в полном body; выбранные целые chunks добавляются тем же packer, исходник/вопрос/история не обрезаются сервером. Если минимальный body не помещается либо ни один найденный chunk не помещается, возвращается context_budget_exceeded до generation. selected/omitted counts отличают отсутствие знаний от отброшенного по бюджету evidence.

Число bytes не является числом tokens. Day 30 гарантирует заданный num_ctx/num_predict и byte caps, но не универсальную гарантию token fit всех максимально допустимых файлов. Это явно отражается в документации и проверках; synthetic live fixtures короткие. Exact tokenizer/template preflight оставлен дальнейшему развитию и не подменяется эвристикой chars/4. Успешный формат/цитаты не доказывают, что upstream не усёк вход.

Логи приложения — только allowlist: request_id, fixed route ID, safe client label, status/error code, elapsed/retrieval/generation durations, token counts, active/max_active, selected/omitted counts. Не логировать raw URL/query, headers, ID произвольного ввода, код, вопросы, ответы, history, цитаты, filenames, абсолютные пути, source/input hashes и содержимое exception. Обычный Uvicorn access log выключен, httpx debug/trace и Ollama request-body logging выключены; внешние proxy logs также без содержимого/Authorization. Token label задаётся владельцем, не клиентом. Проверки с уникальными canary markers покрывают app/server/client error paths. Техническое evidence хранит только разрешённые метаданные, не transcript.

### 6. Two requests, native queue and honest cancellation

Baseline Ollama: `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_QUEUE=2`, `OLLAMA_MAX_LOADED_MODELS=1`. Это операторский профиль для контролируемой демонстрации, не автоматическая правка глобального Ollama config при старте сервиса. Не проводить CLI inference и чужие эксперименты одновременно с приёмкой. Переключение parallel=2 не обязательно для Day 30 и не входит в базовый live-budget.

Async HTTP boundary делает fail-fast admission до передачи sync core в ограниченный thread pool. Два допущенных вызова могут одновременно ждать локальную Ollama; дальнейший chat сразу получает 503 capacity_exceeded с Retry-After. Нет Redis/Celery, durable jobs, дополнительных Ollama instances, application semaphore waiters без границы или очереди futures. Health/status работают вне двух inference slots.

Connect к Ollama — 3 s; I/O timeouts конечные; абсолютный deadline принятого chat — 120 s, включает core/retrieval/metadata/ожидание Ollama/ответ/validation, но не предшествующее получение HTTP-body. Клиентский timeout — 135 s. Read timeout httpx сам по себе не абсолютный deadline. Watchdog отвечает 504 к deadline, но ownership фоновой sync-операции и slot продолжают учитываться до её действительного окончания. Не создавать replacement worker после каждого timeout и не считать cancel await остановкой потока.

Если клиент отключился, новых retries нет; операция остаётся учтённой, пока есть возможность получить bounded upstream outcome. Если inference был отправлен, но completion неизвестен после ошибки/timeout, admission переходит в recovery_required: новые chat получают 503, readiness — 503, health остаётся 200. Поздний подтверждённый terminal response позволяет освободить соответствующее неизвестное состояние; иначе оператор проверяет/восстанавливает выделенную Ollama перед возобновлением. Сам по себе `/api/ps`, истечение cooldown или перезапуск FastAPI не считаются доказательством завершения. Удалённого reset/kill endpoint нет. Автоматического убийства чужого runner/всех Python/Java процессов нет.

Graceful shutdown прекращает допуск и ограниченно дожидается собственных операций; если завершение не подтверждено, это фиксируется безопасным кодом и описывается оператору. Строгая отмена server inference не обещается. In-memory limits предполагают один процесс сервиса; multi-worker deployment вне scope.

### 7. Private remote demonstration is optional infrastructure

Основная функциональность полностью работает через localhost без VPS, публичного IP/домена, port forwarding и Tailscale. Основной удалённый вариант после отдельного подтверждения установки/настройки — Tailscale Serve, HTTPS reverse proxy только к порту приложения; tailnet policy ограничивает устройства/пользователей и порт. Не публиковать каталоги, Knowledge, Workspace или Ollama endpoint. Сервис по-прежнему loopback-bound; Bearer auth обязателен также внутри tailnet. Наличие HTTPS/Tailscale не меняет границы данных.

Serve не равен публичному доступу. В README/evidence фиксируется: доступ со второго устройства из другой сети через интернет по приватной VPN, а не public-IP hosting. Автор челленджа упомянул внешний IP и предпочёл два устройства, но явно не подтвердил VPN; одобрение выбранной пользователем архитектуры не выдаётся за подтверждение автора. VPS/public IP не становятся задачами или блокерами основной реализации.

Tailscale Funnel — только документированная отдельная временная возможность при последующем запросе публичного HTTPS. Он не включается установкой Serve или запуском приложения, не является обязательной проверкой/задачей Day 30. Перед включением отдельно согласовываются публикация, срок, token/ограничения, проверка выключения и отсутствие утечки log content. Сетевой клиент не должен использовать TLS verification disabled.

Остановка: отключить только созданный для Day 30 Serve route, проверить его недоступность, завершить HTTP-процесс и удалить/отозвать его token при необходимости. Не сбрасывать чужую конфигурацию Tailscale, не удалять Knowledge/index/models. CLI и Ollama продолжают работать. Автозапуск/Windows service/Docker не требуются.

### 8. Verification and acceptance boundaries

Offline: focused HTTP tests, fake Ollama, filesystem safety, fresh/corrupt index, strict input limits, fake-clock rate limits, deterministic barriers для двух запросов и третьего отказа, timeout/disconnect ownership, safe logs, runtime regression и CLI-only environment. Отдельный loopback TCP test с двумя независимыми клиентами и fake upstream проверяет реальный HTTP, но не GPU или два устройства. Не запускать старый backend/Android/Gradle ради этих изменений.

Live только после отдельного запроса пользователя, на Windows и synthetic fixtures. Перед ним — read-only preflight версии/digest/local-only/Knowledge/портов; никаких скрытых warm-up calls. Бюджет основной серии: максимум 6 chat generations: локальный вопрос+уточнение (2), локальная конкурентная пара (2), удалённая пара с двумя физическими устройствами, одно из другой сети (2). Первый запрос учитывает cold load, не отдельный preload. Auth/oversize/rate/capacity проверки преимущественно fake/offline и не должны вызывать дополнительную generation. Индексация synthetic Knowledge, если нужна, отдельно объявляется embedding inference и требует live-разрешения; её вызовы считаются отдельно. При имеющемся подходящем актуальном индексе повторной индексации нет.

Stop-on-error: timeout/OOM/unknown cleanup/invalid model output останавливают серию, новые вызовы не выполняются для красивого результата. Исправление транспортного дефекта и повтор live обсуждаются отдельно; model output failure не маскируется fallback на чат без Knowledge или Day 29 schema.

Дополнение к бюджету от 2026-10-11, после review первой конкурентной пары: исходный
потолок был 6 generations, из них использованы 4 (диалог 2 + первая пара 2).
Пользователь отдельно разрешил ровно одну дополнительную локальную пару с более
узкими вопросами, без изменения runtime/model/limits. Новый перспективный потолок
— 8: диалог 2 + первая пара 2 + дополнительная пара 2 + резерв remote 2.
Это отдельный сценарий, не воспроизведение исходной пары; исходный FAIL сохраняется.
При новом техническом отказе локальные конкурентные эксперименты прекращаются,
6.3 остаётся открытой. Remote-резерв не разрешает запуск без отдельного подтверждения.
Подробности — [additional concurrent evidence](live-concurrent-additional-2026-10-11.md).

Evidence различает: принятые HTTP-интервалы и max_active=2; передачу upstream; ожидание очереди (если непосредственно не наблюдалось — unavailable/inferred, без придуманной длительности); реальный inference parallelism (не требуется, не выводится из пересечения HTTP); завершение done/stop и валидацию каждого ответа. Technical PASS требует успешного первоначального хода, уточнения и обеих ответов пары; корректно возвращённая 502 — PASS теста обработки ошибки, но не PASS успешной live-пары. Semantic review записывается отдельно как PASS/PARTIAL/FAIL/NOT_EVALUATED и не выбирает модель за Day 29.

Core/local acceptance и remote demonstration отмечаются отдельно. Если установка/настройка Tailscale ещё не подтверждена или второе устройство недоступно, удалённая задача остаётся pending, локальная реализация продолжается; нельзя объявлять её выполненной по двум процессам одного ПК. Mac M1 не входит в обязательные checkbox tasks. Видео в рамках текущего Proposal и автоматической offline-реализации не записывается; фактическая демонстрация/запись — отдельный этап пользователя.

## Risks / Trade-offs

- [Coder 7B ошибается по существу] -> оставить NO SUITABLE PROFILE CONFIRMED, явно отделить механическую validation и semantic verdict, не менять историю Days 27–29.
- [История содержит injection/старые ошибки или устаревшие сведения] -> только data field, текущие evidence и валидатор, без tools; иммунитет модели не обещается.
- [Уточнение не содержит поисковых терминов] -> включить последний user-вопрос и file stem в bounded deterministic FTS5 query; assistant history не evidence; показать недостаток знаний при отсутствии hits.
- [Byte budget не гарантирует token fit] -> фиксированный num_ctx и отдельные byte caps, короткие live fixtures, явно ограниченная гарантия; exact tokenizer позже.
- [Thread/runner продолжает работу после timeout] -> удержание ownership, recovery_required и отсутствие retries/нового допуска при неизвестном completion.
- [Локальная подмена файлов/смешение с чужой нагрузкой] -> доверенный read-only synthetic corpus и выделенное окно проверки; path reader не OS sandbox.
- [VPN зависит от внешней координации] -> необязательная инфраструктура, локальный CLI/HTTP независимы; доступ через VPN не называется публичным hosting.
- [Модель/индекс могут занимать RAM и загружаться долго] -> два допуска, один model runner baseline, явные deadlines; keep_alive сохраняет резидентность, не является памятью диалога.

## Migration Plan

1. При Apply зафиксировать исходные изменения и исторические hashes, выделить общий сценарий с regression tests без изменения старых контрактов.
2. Добавить optional HTTP installation/launcher и клиент; core CLI должен запускаться без HTTP-пакетов и без FastAPI/Tailscale.
3. Настроить локальный synthetic allowlist и secrets вне Git; existing Knowledge index создаётся владельцем, не startup hook.
4. Пройти offline tests, затем по отдельному разрешению Windows live. Установка Tailscale/удалённая демонстрация — отдельный gate.
5. Создать краткий Day README и ссылку из корневого README; технические инструкции хранить в README HTTP-компонента и общей утилиты, без переписывания исторических результатов.
6. Rollback сетевого режима: убрать только Day 30 route, остановить HTTP, отозвать токены. CLI, Knowledge и Ollama не удаляются и не зависят от отката. Удаление optional HTTP environment не ломает CLI.

## References

- [FastAPI sync/async](https://fastapi.tiangolo.com/async/), [HTTPX timeouts](https://www.python-httpx.org/advanced/timeouts/), [Uvicorn resource limits](https://uvicorn.dev/settings/).
- [Ollama concurrency/local-only](https://docs.ollama.com/faq), [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve). Эти источники исследованы на этапе Explore; фактические версии/настройки проверяются перед live, конфигурация автоматически не применяется.
