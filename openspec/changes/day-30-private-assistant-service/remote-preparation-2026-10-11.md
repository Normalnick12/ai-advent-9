# Day 30 — подготовка Android remote-проверки, 2026-10-11

## Подтверждённый remote HTTPS health

Пользователь вручную подтвердил: личный Android подключён к той же tailnet через
мобильный интернет, Wi-Fi выключен. Браузер открыл фактический HTTPS /healthz
из Serve status и показал {"status":"ok"} без предупреждений TLS.
**Remote HTTPS health PASS — user-observed.** Это не подтверждает Bearer auth,
readiness, HTTP concurrency между устройствами или работу модели.

Предыдущая попытка Windows self-HTTPS закончилась TLS handshake timeout через
5 секунд; причина не установлена. Тогда маршрут и FastAPI были остановлены.
Пользователь отдельно разрешил повторную временную настройку для проверки Android.
Это не inference retry. Результат Android не переписывает прежний timeout.

## Проверенное состояние и временный токен

Serve status подтверждает только HTTPS 443 → http://127.0.0.1:8030, tailnet only.
Funnel не включён; Ollama остаётся на 127.0.0.1:11434. Чужих маршрутов перед
созданием не было. Глобальная конфигурация VPN/firewall/router не менялась.
Tailscale 1.104.1; MagicDNS и CertDomains ранее подтверждены. Старые Health warnings
сохранялись при успешной отдельной проверке coordination HTTPS и TS2021 handshake;
они не объявлялись устранёнными или доказательством недоступности Android.

Создан отдельный криптографически случайный 256-bit URL-safe Bearer телефона:
label phone_temp, env LAA_DAY30_PHONE_TOKEN. Значение не выводилось в tool output,
чат, Git или evidence. На диске только Windows DPAPI ciphertext в ignored
.local/day30/phone-token.dpapi. В ignored config.json добавлена только env-ссылка;
прежний token local_live сохранён. Исходники runtime не менялись.

Перед перезапуском HTTP подтверждены active=0/recovery_required=false; остановлен
только прежний FastAPI, Serve сохранён. Новый FastAPI запущен на loopback с обоими
токенами. GET /readyz с телефонным токеном локально: **200 {"ready":true}**;
тот же GET без токена: **401**. Это локальные auth-проверки, не Android PASS.
Проверки не вызывали chat generation, embeddings или загрузку модели.

HTTP Shortcuts на телефоне: обычный GET /readyz по фактическому Serve HTTPS URL,
Bearer authentication, пустое тело, стандартная TLS verification. Секрет вводится
пользователем вручную из отдельного локального PowerShell без записи/транскрипта;
он не передаётся через чат, web editor или экспорт настроек.

## Проверки и открытые условия

- Focused offline regression: **66 passed**, 2.69 s; известный warning
  Starlette TestClient/httpx, без production code changes.
- Remote HTTPS health PASS; remote authorized readiness **PASS**: пользователь
  подтвердил получение {"ready":true} на телефоне после настройки Bearer GET;
  сервис зафиксировал соответствующий новый ready/status=200, request_id
  8e724061619544dd9b7f505c4bcba793. Проверка модели не выполнялась.
- Задачи 7.1–7.4 пока открыты; OpenSpec **29/33**. Полная 7.1 требует оставшихся
  remote auth/access checks, а 7.2 — согласованной пары физических клиентов.
- Бюджет **6/8**: в этом этапе chat generations **0**, embeddings **0**.
  Два оставшихся calls не запускаются до подтверждения готовности телефона.
- Serve и HTTP намеренно оставлены работающими по запросу пользователя для
  следующего GET. После согласованной демонстрации отключить только этот маршрут,
  остановить HTTP и отозвать временный телефонный токен; cleanup пока **PENDING**.
- Commit/push/archive/video не выполнялись. Coder 7B остаётся техническим кандидатом,
  Day 29 NO SUITABLE PROFILE CONFIRMED сохранён.

## Подготовленная координация, ещё без запуска

Клиент A (Windows) задаёт прежний узкий synthetic вопрос о раннем возврате EmptyCart
до PaymentGateway; клиент B (Android) — о корзине и навигации при отклонении платежа.
Оба используют checkout-demo, history=[], исходную HTTP schema и прежние настройки.
Дословные вопросы совпадают с отдельно разрешённой дополнительной локальной парой;
это отдельная remote-демонстрация, не попытка улучшить model output.

Пользователь сначала подготавливает POST в HTTP Shortcuts и подтверждает готовность,
не отправляя его. После подготовки наблюдения и явного сигнала пользователь
однократно отправляет B. Windows-клиент должен отправить A сразу после наблюдаемого
допуска B, пока B ещё обрабатывается. Health/status и раздельные request_id фиксируются
как метаданные. Повторов, дополнительных generations или увеличения лимита нет.
На этом шаге ни один POST /v1/chat не запущен; общий расход остаётся 6/8.
