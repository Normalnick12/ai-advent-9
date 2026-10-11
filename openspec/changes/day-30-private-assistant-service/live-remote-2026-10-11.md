# Day 30 — Windows + Android remote-пара, 2026-10-11

## Scope и бюджет

После подтверждённого Android HTTPS health и Bearer readiness пользователь
подготовил POST в HTTP Shortcuts и сообщил «POST готов, не отправлял».
Разрешена единственная remote-пара, ровно два оставшихся generations из потолка 8.
Android использует мобильный интернет с выключенным Wi-Fi и Tailscale; Windows
обращается к loopback API. До отдельного сигнала POST не запускались.

Production runtime, prompts, schema, RAG, model settings и limits не менялись.
Временный ignored observer ограничивал demonstration двумя generations и одним
разрешённым вопросом каждого клиента. Это test harness, не новая production queue.
Два вопроса дословно совпали с дополнительной локальной парой: A — EmptyCart до
PaymentGateway, B — корзина/навигация при declined payment; checkout-demo, history=[].

## Preflight и согласованная отправка

- Synthetic CheckoutCoordinator.kt/checkout.md совпали с прежними fixtures;
  index fresh, corpus hashes сохранены и после проверки не изменились.
- Coder digest `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
  Ollama local-only 127.0.0.1:11434, parallel=1; нет resident models, runner или
  outstanding operations перед запуском. GPU: 723 MiB / 5%.
- Serve status: только private HTTPS443 → 127.0.0.1:8030; Funnel выключен.
  FastAPI остаётся loopback; телефон имеет отдельный Bearer, Windows — прежний.
- Перед заменой HTTP launcher на тот же launcher с observer: active=0,
  recovery_required=false. Serve сохранён; после restart локальная readiness 200.
- Windows-клиент ожидал до 300 s, читая metadata-файлы, без polling model API.
  После пользовательского сигнала телефон отправил B. Наблюдение подтвердило
  admission B и active=1; Windows немедленно отправил A ровно один раз.

## Наблюдаемые результаты

| Метрика | A: Windows | B: Android, исходная операция |
|---|---:|---:|
| request_id | 03253cbcb54f4f1f93686ded3f5b36ed | 71681793b2a84d70889bed37afbbdf48 |
| Receipt, observer-relative s | 62.927104 | 62.820424 |
| Upstream submission, observer-relative s | 62.957058 | 62.856335 |
| HTTP handler wall | 11.966841 s | 10.001096 s |
| Windows client wall | 11.977052 s | unavailable |
| HTTP handler outcome | 200 | 504 request_timeout |
| Успешный ответ получен клиентом | да | нет |
| Ollama request bytes | 7268 | 7248 |
| Prompt / output tokens | 1291 / 828 | 1289 / 904 |
| Ollama done / reason | true / stop | true / stop, позже HTTP disconnect |
| Mechanical validation | passed | passed, позже HTTP disconnect |
| Provider total | 11.932299 s | 22.612318 s |
| Provider load | 2.255940 s | 2.356427 s |
| Provider prompt evaluation | 0.287365 s | 0.174092 s |
| Provider generation evaluation | 9.377865 s | 10.360902 s |

Оба payload содержали четыре текущих Markdown chunks; параметры
num_ctx=8192, num_predict=2048, temperature=0, seed=28 проверены наблюдателем.
Ни embeddings, ни warm-up, ни индексирование не выполнялись.

Два `operation_admitted`, max_active=2, оба запроса одновременно в обработке.
Health во время двух активных операций: HTTP 200 за **1.232 ms**.
Связь question → runtime operation → request_id проверялась отдельно для клиентов.
Для A digest результата совпал с собственным HTTP envelope и полученным ответом.
Для B подтверждён собственный upstream/validation result, но успешного HTTP
envelope на Android нет, поэтому полная end-to-end проверка раздельных ответов
не выполнена. Перестановки upstream результатов не обнаружено.

### Android timeout и дополнительная HTTP-попытка

Исходное ожидание B закончилось через 10.001 s с request_timeout. По коду штатный
chat deadline=120 s; `Service.chat` также возвращает этот код при ASGI disconnect.
Body уже был принят и upstream отправлен, поэтому это не body_timeout.
В данном пути раннее завершение соответствует disconnect между proxy/client и
FastAPI. Конкретная первопричина на Android или proxy не установлена; 10 секунд
не выдаются за измеренную настройку HTTP Shortcuts.

Позже зарегистрирован ещё один HTTP POST с request_id
`7ec41b372fc34e0bb481248fb2fd8736`, HTTP **503 capacity_exceeded**. Пользователь
подтвердил именно этот статус, error code и request_id на Android.
Это отказ временного demonstration guard до нового admission/inference: guard
отклоняет повторный либо неразрешённый вопрос. Он не логировал тело, поэтому
точное содержимое дополнительного POST не восстановлено. Не установлено, был ли
он автоматическим повтором клиента/proxy или отдельным действием; не приписывать
причину пользователю без evidence. Windows-клиент отправил ровно один POST.

Этот 503 не называется штатным production capacity test: на тот момент A уже
завершился, B продолжал выполняться, recovery_required=true. Новая генерация не
началась. Не заявляется доставка исходного server-side 504 телефону: подтверждён
клиентский 503 другой попытки. Всего наблюдаются три HTTP chat attempts, два
admissions и ровно два реальных generations.

### Ownership и завершение

После disconnect B slot удерживался. После окончания A журнал показывал
active=1/recovery=True. B продолжил работу и завершился done/stop, validation
passed на observer offset=85.471042 s. Только после terminal completion B
подтверждены active=0, max_active=2, recovery_required=false.
Status ready=false отражал инвалидированный/истёкший cache, не новый readiness probe.
Ollama log: ровно два POST /api/chat 200, /api/embed=0, runner n_seq_max=1.
Точное время/глубина очереди unavailable; HTTP overlap не доказывает GPU parallelism.
Порядок admission/upstream submission не выдаётся за FIFO исполнения модели.

GPU во время: 5817 MiB / 95%; после: 5890 MiB / 3%. Это отдельные снимки, не пики.

## Verdicts

- Локальная техническая приёмка: прежний PASS сохраняется вместе с первым FAIL.
- Приватный HTTPS с Android и авторизованный readiness: **PASS** по ручному
  подтверждению пользователя и service metadata; публичный доступ не включался.
- Два физических клиента и HTTP concurrency: **PASS**, admitted=2/max_active=2.
- Два успешно доставленных ответа remote-пары: **FAIL / NOT CONFIRMED**.
  A получил 200, Android подтвердил 503 дополнительной попытки.
- Модель: оба внутренних результата done/stop/mechanical PASS. A semantic **FAIL**:
  видимый ответ неверно отрицает вызов PaymentGateway в продолжении checkout.
  B не доставлен пользователю, отдельного review текста в этом remote-прогоне нет;
  semantic **NOT_EVALUATED** для remote-доставки. Метаданные digest обоих synthetic
  results совпадают с предыдущей узкой локальной парой, что не повышает model status.
- Day 29 **NO SUITABLE PROFILE CONFIRMED** неизменён.

Raw model output/вопросы/токены в технических файлах не сохранялись. Полный synthetic
ответ A просмотрен только в stdout клиента. Safe observer и service metadata
находятся в ignored `.local/day30/remote/`; B raw output не сохранялся.

## Безопасное выключение

После terminal completion обеих operations выполнено только
`tailscale serve --https=443 off`. Serve JSON стал {}, Funnel status — No serve config.
HTTPS /healthz с Windows после выключения: connection refused, HTTP status 000.
Отдельное подтверждение выключения браузером Android не получено; конфигурация
маршрута, отказ подключения и отсутствие HTTP listener проверены на Windows.

FastAPI штатно остановлен: service_stopped active=0 recovery=False; listener8030=0.
Телефонная env-ссылка phone_temp удалена из ignored config, phone-token.dpapi
удалён; оба процесса, державших этот секрет в environment, завершены.
Токен телефона отозван для последующих запусков. Пользователю следует удалить
его из HTTP Shortcuts. Прежний local_live, CLI, Knowledge/index и Ollama сохранены;
Ollama по-прежнему слушает 127.0.0.1:11434. Global Serve reset не использовался.

Итоговый бюджет: **8/8 generations**, новых embeddings 0. Повторов model inference
и увеличения бюджета нет. Дальнейшие live-эксперименты остановлены.

## OpenSpec

7.2 остаётся открытой из-за отсутствия двух успешных remote ответов.
7.1 остаётся открытой: HTTPS/auth положительно проверены, но весь набор отрицательных
проверок недоступности Ollama/каталогов именно со второго устройства и review
tailnet access policy не завершён. Offline/local проверки не подменяют их.
7.3 закрыта по проверенному удалению маршрута/остановке/сохранности локальных данных.
7.4 закрыта после фактического обновления README/evidence и финальных checks.
Итог: **31/33**, без искусственного полного PASS. Mac NOT TESTED; commit/push/archive
и видео не выполнялись.

## Финальные проверки

Focused offline regression: **66 passed**, 2.88 s, один прежний warning
Starlette TestClient/httpx. Python syntax temporary harness, Markdown links,
revoked-token/config/budget checks — **PASS**. OpenSpec strict validation **PASS**,
git diff --check без ошибок. Production code не изменялся; исторические fixtures,
результаты и незакрытые задачи Days 27–29 сохранены.
