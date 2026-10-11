# Day 29 — ограниченный Windows live, остановка для review

2026-10-10. Reviewer: **assistant provisional; user review pending**. Окончательный кандидат не выбран. Это ограниченная серия после явного подтверждения пользователем установки обеих моделей и local-only режима. Предыдущий offline checkpoint в validation.md сохраняется как история.

## Что выполнено и почему остановлено

Qwen3 4B прошла load/readiness и S1, затем получила технический отказ на S2 из-за недействительной ссылки на observation ID. Её S3–S6 не запускались. Независимый admission Qwen2.5-Coder 7B достиг 60-секундного wall-clock deadline; дочерний клиент был прекращён и reap подтверждён. Coder S1–S6 не запускались. Весь live остановлен из-за `server_cleanup=unknown`.

Это **два разных отказа**: структура ответа Qwen3 и незавершившийся admission Coder. Нельзя утверждать, что обе модели демонстрируют одинаковую нестабильность Ollama. Нельзя сравнить качество моделей по отсутствующим ответам Coder или объявить Qwen3 победителем.

## Identity и фиксированные условия

| Модель | Полный installed digest |
|---|---|
| `qwen3:4b-q4_K_M` | `2bfd38a7daaf4b1037efe517ccb73d1a3bbd4822cf89f1a82be1569050a114e0` |
| `qwen2.5-coder:7b-instruct-q4_K_M` | `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364` |

Оба digest и profile hash сверены до/после, без изменений. Ollama 0.40.2; RTX 4070 SUPER, driver 610.88, reported VRAM 12282 MiB. Q4_K_M; num_ctx=8192, num_predict=2048, temperature=0, seed=28, keep_alive=5m, stream=false. Explicit sampling: top_k20/top_p0.95/min_p0/repeat_last_n64/repeat_penalty1/presence_penalty0/frequency_penalty0. Qwen3 think=false, Coder thinking не поддерживает и поле не получает. Прикладные prompt/schema и frozen manifest не менялись. Prompt corrections: **0**.

Полные API-resolved profiles с provenance, native template hashes и inherited stop fingerprints, timestamps и все доступные metrics — в [live-evidence-2026-10-10.json](live-evidence-2026-10-10.json). Templates и inherited stop отличаются: это сравнение двух модельных конфигураций, не только весов. Backend activation и действующие server concurrency settings не подтверждены этими API и остаются unavailable. Metadata сообщает runner ggml; это само по себе не доказательство CUDA backend. Настройки сервера не менялись.

Frozen manifest SHA-256: `afb74eed9bfacf85576c53aeeee2b56be274446d21a5ff5c62dde789f08aa4d4`. Retrieval/index не выполнялись; одинаковые заранее выбранные chunks S1–S6 проверены offline. Runtime-код, settings и fixtures во время серии не менялись.

## Технические результаты и время

| Модель / операция | Наблюдение перед запросом | Время операции | Полное bounded client wall | Outcome |
|---|---|---:|---:|---|
| Qwen3 load-only | not resident | admission HTTP 3.551 s | 3.870 s | done/load; ps digest + ctx8192 подтверждены |
| Qwen3 S1 | resident | generation HTTP 15.380 s | 15.707 s | done/stop, source/schema PASS |
| Qwen3 S2 | resident | generation HTTP 20.932 s | 21.242 s | done/stop, source/schema FAIL: dangling observation reference |
| Coder load-only | not resident на preflight; child snapshot потерян при отмене | цензурировано deadline 60 s | 60.017 s | client deadline, client_reaped=true; runner unknown |

Admission Qwen3 был cold по отсутствию резидентности, но состояние OS disk cache неизвестно. Последующие S1/S2 наблюдались resident; provider load_duration 0.0051/0.0046 s. Это не обычная cold CLI latency: preload выполнен отдельно. Задержка ответа S1/S2 не TTFT; TTFT unavailable.

Provider S1: prompt_eval_count725, eval_count283, prompt_eval0.730 s, eval14.635 s, total15.379 s. S2: prompt_eval_count1302, eval_count862, prompt_eval0.293 s, eval20.572 s, total20.931 s. При желании decode rate вычисляется из eval_count/eval_duration; он не компенсирует пропуски или технический отказ. Нельзя складывать provider total, load и client wall: интервалы пересекаются.

Retrieval time в frozen generation — 0 по конструкции эксперимента, **не измерение скорости RAG**. Полный реальный пользовательский цикл query embedding → retrieval → generation не запускался. Provider counters/time Coder unavailable, а 60 s — не успешное время загрузки.

Счёт: **4/32 load/chat attempts** = 2 load-only + 2 chat. Load success1/2; validated chat1/2. Из 12 основных scenario slots: 1 technical PASS, 1 technical FAIL, **10 NOT RUN**. Metadata worker2/2 completed учитываются отдельно. Unknown-server timeout1; unmatched start/end0; retries0; historical9B calls0; embedding/index calls0. Суммарное bounded client time, включая metadata: **101.314/5400 s**. Бюджет не исчерпан; продолжение запрещает stop condition, а не нехватка времени.

Поздний read-only ps показывает Qwen3 resident, Coder not resident. Это **не доказывает**, что незарегистрированный/загружающийся runner Coder завершился. Журнал продолжает блокировать дальнейшие live-вызовы. Ollama и посторонние процессы не завершались и не перезапускались.

## Память — только snapshots

Qwen3 ps после admission и перед S1/S2: size=size_vram=3,996,867,624 bytes (~3.72 GiB), ctx8192. System-wide VRAM before/after admission: 6530 → 10531 MiB; S1: 10531 → 10557; S2: 10557 → 10559. Заметная исходная VRAM занята уже до запуска; она не приписывается Qwen3 и может влиять на headroom последующего admission. Причинная связь с timeout Coder **не установлена**.

System RAM total34,191,245,312 bytes (~31.84 GiB); available before/after Qwen3 admission22,177,120,256 → 21,391,093,760 bytes; после S2 21,120,237,568 bytes. Это system available RAM, не process RSS. Runner RSS/process commit unavailable. Coder snapshots/counters не дошли до родителя при deadline и остаются unavailable. Никаких заявлений о peak, стабильном потреблении памяти или работе рядом с Android Studio из этих точек не делаем.

## Предварительная смысловая оценка для совместного review

Сверка с неизменённой Day 28 rubric и [Day 29 supplement](../../../day-29-local-assistant-optimization/rubric.md). Ответы целиком/ reasoning в отчёт не копируются; ниже только проверяемые verdicts.

| Пункт | Qwen3 S1 (без Knowledge) | Qwen3 S2 (checkout rules) |
|---|---|---|
| C1 dependencies, без выдуманной реализации | correct | correct, преимущественно переписан исходник |
| C2 empty до charge | correct | correct; применение R2 к этой ветке обосновано |
| C3 сумма/charge/declined до mutations/navigation | partial: сумма/charge/approval есть, declined boundary явно не раскрыта | partial: charge/declined видны, расчёт суммы опущен |
| C4 clear → receipt → Success после approval | **missing**, успешный путь не объяснён | partial: after-approval clear/navigation упомянуты только в application; Success и точная последовательность не объяснены, ссылка на observation недействительна |
| C5 границы знания / guarantees | partial: реализации dependencies неизвестны; исключения/transaction не обсуждаются | largely correct limitations: нет evidence rollback/retry/idempotency/recovery; реализации dependencies неизвестны |
| R1 responsibility | not applicable | literal support correct; application о sequencing ссылается на declaration dependencies, а не observation с последовательностью вызовов |
| R2 success boundary | not applicable | literal support correct; empty application correct; after-approval application ломает provenance reference |
| R3 evidence limits | not applicable | missing как cited rule; смысл частично отражён в limitations |
| Unsupported claims / Kotlin error | 0 обнаруженных явных false claims; это не полнота ответа | **1 явное противоречие исходнику:** CheckoutResult назван enum в assumptions, хотя показан sealed interface |
| Другие assumptions | нет | тип результата items() как list не установлен исходником; помечен assumption, не подтверждённый факт |
| Общий provisional verdict | **PARTIAL**: полезное, но неполное объяснение | **FAIL**: provenance нарушен + ошибка Kotlin; ограничения сформулированы частично верно |

Точная причина technical FAIL S2: третье code_observation имеет ID `)`, а третье application содержит `observation_ids=["3"]`; ID `3` не объявлен. Необычное имя ID само по себе допустимо: ошибка — несуществующая ссылка. Автоматического repair или смягчения validator не было. Две R1/R2 цитаты совпадают с предоставленными spans; верность цитат не исправляет provenance/application defect. Ответ S2 преимущественно по-английски, хотя prompt просит русский; это дополнительное ограничение удобства.

S3 scope conflict, S4 missing knowledge, S5 injection и **S6 Compose lifecycle/StateFlow — NOT RUN** для Qwen3 из-за S2 gate. Все C/R/K/Compose пункты Coder — NOT RUN из-за admission deadline. Число unsupported claims для этих отсутствующих ответов unavailable, не 0. Корректность Android-архитектуры основного набора не подтверждена ни для одного кандидата.

## Что требуется решить вместе

Сначала review S1/S2 и фактов остановки. Финальный выбор, RAG, keep_alive/num_predict/num_ctx/temperature оптимизации пока не выполняются. Q4/Q8 и Mac — NOT TESTED.

Если продолжать после review: отдельно подтвердить завершение относящегося к Coder runner по ограниченным runtime/log/process evidence, не считать ps достаточным и не очищать журнал ради обхода gate. Затем обсудить ограниченную диагностику Coder без повторного 9B либо одну адресную prompt-коррекцию Qwen3 для устойчивых observation IDs и правильного чтения Kotlin. Пока ни диагностика с новыми probes, ни correction/retry не выполнялись. Исходные FAIL остаются в истории; смена профиля потребует явного plan/review и оставшегося бюджета.

Код не менялся, поэтому прежний offline результат **258 passed / 1 skipped** относится к той же реализации и не запускался повторно без причины. Финальная проверка этого этапа: metadata/frozen hashes, evidence JSON, OpenSpec strict validation, scoped docs checks и сохранность исторических Day 27–28. Commit/push/archive/видео не выполнялись.
