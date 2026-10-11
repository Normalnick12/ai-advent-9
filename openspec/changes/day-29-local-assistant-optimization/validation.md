# Day 29 — offline implementation checkpoint, 2026-10-10

Это сохранённый offline checkpoint. Последующая разрешённая серия, установленные digests и причины остановки описаны в [live review](live-review-2026-10-10.md); статусы ниже относятся к моменту до установки моделей.

## Scope and factual status

Реализован доступный offline-этап. Live не разрешён до отдельного подтверждения установки моделей. Не выполнялись pull, inference, новые warm-up исторического Qwen3.5 9B, Git commit/push, archive или запись видео. Это не отчёт о качестве локальных моделей.

Изменения общей утилиты ограничены opt-in temperature/keep_alive, передачей overrides при упаковке и безопасными фазовыми metrics. Defaults/prompt/schema, source validator, retrieval, embeddings, SQLite и Workspace сохранены. Driver использует те же pack/parse/render, metadata, retrieval и index; он принимает только наши S1–S6, не является новым CLI-продуктом.

## Offline evidence

- Focused этапы: 32 passed, затем 35 passed после проверок межзапусковых gates; итоговый полный suite включает 36 новых тестов, в том числе оба неуспешных admission без дальнейших вызовов.
- Полный offline suite: **258 passed / 1 skipped**, Python 3.14.7, httpx 0.28.1, pytest 9.1.1. Команда из Day 27: `py -3 -B -m pytest tests ../day-29-local-assistant-optimization/tests -q -p no:cacheprovider`. Это новые результаты Day 29, не замена исторических 222/1 Day 28.
- Реальный зависший тестовый child (sleep, без сети) прекращён через kill/communicate/reap. Проверены timeout/cancel, отсутствие retries, incomplete start, лимиты попыток/времени, unknown server cleanup, запрет повторения закрытой ветки.
- Mock integration проверяет frozen generation без embedding, отдельный RAG с существующим index/query embedding/retrieval, inherited parameters/digest drift/remote rejection, JSON length failure и приватность metrics. Mock PASS не доказывает semantic PASS или стабильность Ollama.
- Frozen manifest включает точные hashes вопросов/Kotlin/prompt/schema и выбранных chunk IDs/spans/order/content. Все шесть payload inputs одинаковы для обеих моделей, кроме объявленных model/capability settings. Рубрика не передаётся модели.
- Compose fixture просмотрен по официальным API state/effects/StateFlow. Android-сборка не запускалась: это синтетический исходник для объяснения, не новое Android-приложение.

## Live prerequisites (read-only check)

GET `/api/version` на loopback: Ollama **0.40.2**. GET `/api/tags`:

| Exact tag | Installed digest | Admission / generation / semantic |
|---|---|---|
| qwen3:4b-q4_K_M | unavailable — NOT INSTALLED | NOT RUN / NOT RUN / NOT RUN |
| qwen2.5-coder:7b-instruct-q4_K_M | unavailable — NOT INSTALLED | NOT RUN / NOT RUN / NOT RUN |

`OLLAMA_NO_CLOUD=1` найден в User и текущем client process environment. `.ollama/server.json` отсутствует; в просмотренном хвосте server.log подтверждение текущего server startup environment не найдено. Поэтому local-only намерение настроено, но применение флага уже запущенным daemon **ещё нужно подтвердить перед live**. Loopback и текущий client env сами по себе этого не доказывают. Конфигурация сервера не менялась, перезапуска не было.

Установленные digests, реальные native templates/capabilities и полный effective profile двух кандидатов ещё недоступны. Runtime-specific resolver протестирован на mocks для 0.40.2; неизвестный runtime/default блокирует запуск. API не подтверждает фактическую activation каждого sampler или backend, поэтому `backend=unavailable`, typical_p deprecated и API-resolved scope обозначены явно. Это не обещание битовой воспроизводимости CUDA/Metal.

## Counts, metrics and semantic review

Windows model load attempts **0**, chat attempts **0**, query/index embeddings **0**. Failed/incomplete live attempts **0**; оба admission и 12 scenario slots — NOT RUN (нет моделей/подтверждения). Metadata GET не считается inference. Локальный тестовый sleep-child не является попыткой модели.

S1–S6 для каждой модели: Kotlin facts, documented rules, entailment, scope application, unsupported claims, limitations, Compose lifecycle/StateFlow — **NOT RUN**. Reviewer для будущей оценки: assistant provisional, user pending. Число необоснованных утверждений unavailable, а не 0. Кандидат не выбран; end-to-end S2/S6 и оптимизации — NOT RUN.

В driver разделены admission_seconds, retrieval_seconds (включая query embedding), generation_seconds (HTTP, включая возможный reload), user_request_seconds (путь retrieval/packing/generation/validation с сопутствующими checks), operation_seconds и полный bounded child client_wall_seconds с инструментированием. Provider total/load/prompt/decode durations переводятся из ns в seconds. Пересекающиеся интервалы не суммируются. Холодная загрузка определяется по ps до admission; keep_alive=5m не доказывает residency и не исключает reload. TTFT unavailable для stream=false. Timeout — censored client wall observation, не успешный load/generation time; завершение server runner после отмены unknown.

RAM/VRAM пока не сравнивались для моделей. Инструментирование: Windows GlobalMemoryStatusEx total/available bytes, nvidia-smi system GPU used MiB, Ollama ps model bytes/VRAM/context. Before/after snapshots, **не peak**; runner RSS и process commit unavailable. Нет фонового мониторинга.

## Bounded next stage

1. Получить подтверждение пользователя на установку точных двух tags. После установки записать фактические полные digests и подтвердить local-only **работающего** сервера. Не подставлять registry digest вместо local digest.
2. Зафиксировать реальные profiles. Общий quality baseline Q4_K_M, keep_alive=5m, ctx8192/output2048/temperature0/seed28. Один bounded load/readiness, S1; только после успеха S2–S6. Successful S1 переиспользуется. Failure закрывает configuration, timeout/unknown cleanup всю серию.
3. Предоставить пользователю пофактный review по rubric.md, затем выбирать предварительного кандидата. Приложение не выбирает кандидата автоматически.
4. Только после review подготовить отдельный synthetic Knowledge index и выполнить реальные S2/S6. Index embedding отдельно учитывается и не входит в generation comparison.
5. При обосновании — один фактор относительно baseline, S2/S6: keep_alive0, output1024, temperature0.2. Не смешивать их в одну конфигурацию/таблицу. Full profile parent hash фиксируется в журнале. Повторный RAG после изменения выбранного профиля требует отдельного review/подготовки запуска в пределах оставшегося бюджета; baseline RAG не выдаётся за проверку изменённого профиля.

Driver намеренно не автоматизирует token-fit/ctx4096, prompt correction, последовательное принятие комбинации факторов, Q8 или восстановление после unknown cleanup. Такие шаги требуют обнаруженной причины и небольшого отдельного изменения/операторского решения. Нельзя очищать journal для обхода gate; все failed/incomplete записи сохраняются. При одинаковой нестабильности двух кандидатов предложить отдельное ограниченное чтение runtime/log/driver/memory evidence, не перебирать warm-up бесконечно.

Лимит текущего Windows этапа: 32 load/chat attempts, включая неуспешные/незавершённые, 90 минут суммарного bounded client execution; паузы на review вне таймера. Metadata учитывается по времени отдельно от call budget. Одной загрузкой/парой нельзя обосновать статистическую надёжность или общий выигрыш качества.

## Deferred and target Mac

Q4/Q8 — **NOT TESTED**, оснований для расходования памяти/времени пока нет; выводов о влиянии quantization нет. Thinking остаётся false только при фактической capability, у unsupported модели параметр не отправляется. Изменения prompt ещё не требуются и не выполнены. Исторический Qwen3.5 9B — только контроль из Day 28.

Mac M1 16 GB — **NOT TESTED**, устройство/разрешение недоступны в этом этапе. Отдельный план: выбранный кандидат, максимум 12 load/chat attempts / 45 минут, Android Studio с записанным проектом/нагрузкой, emulator отдельно. Windows-драйвер сейчас считает Windows budget; перед целевой серией применить отдельный Mac budget, не переносить Windows verdict.

Форма Mac observations: actual model digest; Ollama version/backend; Android Studio workload; available unified RAM до/после; memory pressure до/после; swap used до/после и delta; cold/warm classification; S1–S6 technical/semantic status; real RAG S2/S6; время IDE action и субъективная отзывчивость; timestamps/method. Каждый отсутствующий показатель = unavailable. Сейчас все поля NOT TESTED.

## Preservation and completion checks

До изменений сохранены SHA-256 42 исходных файлов в `day-29-local-assistant-optimization/historical-hashes.json`. Разрешённые изменения существующих файлов: `grounded_explain.py`, `rag_cli.py`, `ollama_client.py` и README общей утилиты. Исторические fixtures/rubric/reports и OpenSpec Day 27–28 должны совпадать побайтно. Day 28 остаётся активным с 26/28 tasks; его незакрытые A/B/Mac проверки не закрываются Day 29.

Проверка hashes: 38/42 исходных файлов неизменны, изменены ровно четыре разрешённых файла выше. Day 28: 26 completed / 2 open. Python AST: 8 файлов; 41 относительная ссылка проверена до финальных дополнений отчёта. Frozen manifest совпадает. OpenSpec strict validation PASS; scoped whitespace/diff/secret-pattern checks без замечаний. Рабочий каталог остаётся с незакоммиченными изменениями пользователя Day 27–28 и новыми изменениями Day 29. Tasks: 18/30, оставшиеся 12 относятся к реальным profiles/live/Mac.
