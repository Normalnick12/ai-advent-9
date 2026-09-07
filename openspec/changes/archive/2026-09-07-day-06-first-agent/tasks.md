## 1. Agent behavior and in-memory sessions

- [x] 1.1 Добавить нейтральные ConversationMessage/AgentConfig/LlmResult и минимальный LlmClient contract, SimpleAgent с фиксированной конфигурацией и AgentSession/AgentSessionManager без SDK/HTTP types и циклических импортов; проверить создание двух sessions одного агента с разными IDs, независимой history и одинаковой конфигурацией через unit tests с fake LlmClient.
- [x] 1.2 Реализовать формирование полного context и атомарный commit только completed непустого ответа без refusal; fake-client tests должны проверять точный U1/A1/U2 input, несколько ходов без trimming, повтор instructions, count и отсутствие изменений истории после incomplete/refusal/error/пустого ответа.
- [x] 1.3 Реализовать per-session busy/closed lifecycle с освобождением в finally и немедленным отказом конкурентному turn; deterministic async tests с events должны подтвердить один активный turn в A, отсутствие второго LLM-вызова, возможность параллельного B и освобождение busy после ошибки/отмены до commit.
- [x] 1.4 Реализовать create/get/delete с пустой новой историей, безопасным удалением отсутствующей session и отклонением stale references; tests должны подтвердить удаление факта, отсутствие активного ID и автоматического create после reset, новый ID только при create перед следующей явной отправкой, отказ busy delete, неизвестный старый ID и потерю sessions после создания нового manager как модели backend restart.

## 2. OpenAI Responses adapter

- [x] 2.1 Добавить OpenAIResponsesLlmClient, преобразующий нейтральные сообщения/config в Responses API input; mocked SDK tests должны проверить model gpt-5.6, effort none, max_output_tokens 1200, plain text, store false, полную role history, инструкции каждого turn и отсутствие conversation/previous_response_id/tools/trimming/experiment settings.
- [x] 2.2 Реализовать нормализацию completed/incomplete/refused/error и безопасных кодов/причин по design; tests должны покрывать пустой или непригодный ответ, refusal, incomplete, SDK/API exceptions, отсутствие сырого exception/SDK dump и отсутствие фиктивного reply при неуспехе.
- [x] 2.3 Настроить lazy SDK construction, connect timeout 5 s, timeout/deadline 75 s, max_retries 0 и закрытие клиента; tests с подменённым client должны подтвердить работу create/delete без ключа, максимум один upstream call на turn, отсутствие retry/fallback и корректную отмену без commit.

## 3. Session HTTP API and backend integration

- [x] 3.1 Добавить strict agent DTO и router-local безопасные ошибки: create body {}, message-only body, UUID path, strict string 1–20000 и запрет whitespace-only/extra fields; API tests должны проверить 422 без LLM-вызова и без echo request body/history/instructions/settings/credentials в errors.
- [x] 3.2 Реализовать три endpoints create/send/delete и X-Request-ID: 201 с count 0, 200 с нормализованным turn outcome/count, 204 для delete, 404 session_not_found и 409 session_busy; API tests должны проверить несколько сообщений, reset, потерянную session, счётчик только успешных пар и отсутствие экспорта history/config.
- [x] 3.3 Подключить SimpleAgent, manager и adapter через lifespan/app.state/Depends в существующий backend, не меняя старые services и общие error handlers; regression tests должны подтвердить прежние Day 02–05 payload/contracts/timeout/retry semantics после использования новых sessions и отсутствие новых ключевых зависимостей при app import/health.

## 4. Android data and ChatViewModel

- [x] 4.1 Добавить ChatApiModels, ChatApi и ChatRepository/DefaultChatRepository для create/send/delete, подключить через AppContainer к существующему Retrofit client; JVM tests должны проверить точные URL/body, запрет history/settings в requests, маппинг outcome/404/409/422/transport failures и неизменные budgets/retry настройки старого клиента. Новый domain/use-case слой не создавать.
- [x] 4.2 Реализовать Activity-scoped ChatViewModel с constructor injection: ленивый create при первой отправке, reuse ID, snapshot draft, pending/completed transcript, operation/error/count и duplicate-tap guard; coroutine tests должны проверить create-before-send, отсутствие send при create failure, два последовательных сообщения, failure без повреждения transcript и отсутствие HTTP при одном создании ViewModel.
- [x] 4.3 Реализовать «Новый диалог»: await DELETE 204, затем очистка ID/transcript/draft/count, новый create только при следующей отправке; tests должны проверить успешный reset, локальную очистку без ID, delete 409/transport failure без ложного успеха и отсутствие replay старого текста.
- [x] 4.4 Реализовать lost/uncertain session recovery без idempotency: 404 и неизвестный результат send требуют явного нового диалога, подтверждённый неуспех допускает ручную повторную отправку; tests должны подтвердить сохранение transcript/draft для просмотра, блокировку send при recoveryRequired, безопасный повтор DELETE и отсутствие auto retries/client_message_id/receipt cache.

## 5. Russian chat UI and navigation

- [x] 5.1 Добавить ChatScreen с «Вы»/«Агент», полем «Сообщение», «Отправить», «Новый диалог», loading/error/pending и «Завершённых ходов: N»; Compose tests с fake Repository должны проверить отправку, фактический ответ, reset, count из backend и явные incomplete/refusal/lost-session состояния без backend/API key.
- [x] 5.2 Добавить Day 06 «Первый агент» пятой карточкой в MainActivity/AppRoot/LearningDaysHome и strings.xml с общим заголовком; обновить RootNavigationUiTest для пяти дней, toolbar/system back, доступности каталога без backend и отсутствия автоматических create/send при навигации, сохранив прежние проверки Day 02–05.
- [x] 5.3 Сохранить chat state/операцию при navigation и Activity recreation, scroll при уходе/возврате и сброс scroll после нового диалога; JVM/Compose tests должны подтвердить завершение исходного turn при посещении другого дня без повторного POST/DELETE. Визуально проверить длинные сообщения, узкий экран, крупный шрифт и IME/system insets без перекрытия ввода и действий.

## 6. Documentation and integrated verification

- [x] 6.1 Во время apply создать краткий day-06-first-agent/README.md и актуализировать root/backend/Android README: назначение, зависимости и setup, OPENAI_API_KEY только backend, запуск через scripts/dev.ps1, один backend worker, потеря sessions после restart и сценарий видео. Проверить ссылки, отсутствие секретов и переноса подробного design в Day README.
- [x] 6.2 После реализации выполнить backend pytest и Android unit/build через PowerShell 7 scripts/dev.ps1; подтвердить новые context/isolation/reset/failure/concurrency tests и прежние Day 02–05 contracts без live LLM dependency, исправить выявленные ошибки до перехода к E2E.
- [x] 6.3 После завершения связанных UI/navigation изменений выполнить полный scripts/dev.ps1 ui на переиспользованном эмуляторе; подтвердить chat и navigation regressions без backend/OpenAI, не повторяя успешные проверки без изменения входов.
- [x] 6.4 Отдельно подготовить/переиспользовать управляемую backend session через scripts/dev.ps1 backend, проверить status и доступ с эмулятора, затем выполнить один живой сценарий «сообщить выдуманный факт → спросить факт → новый диалог → спросить без факта» с тремя LLM-запросами. Зафиксировать фактический outcome и счётчики 1/2/0/1 для демонстрации; не требовать точной формулировки и не повторять платные запросы ради неё.
- [x] 6.5 Выполнить openspec validate day-06-first-agent --strict, проверить синтаксис/структуру изменённых файлов, git diff/status, отсутствие секретов и изменений semantics Day 02–05; передать реализованный результат пользователю для проверки без автоматического commit/push/archive.

## Verification note (2026-09-07)

Offline: backend 130 passed; Android JVM 38 passed; debug build successful; full UI suite 17 passed. Live: выполнены ровно три message requests. Первые два completed (counts 1/2), DELETE 204 (count 0), новая session создана только при третьей отправке. Третий turn завершился llm_timeout, count остался 0; повторов не было. После этого пользователь подтвердил успешный ручной live-тест. Задача 6.4 закрыта; все 22 задачи выполнены. Подробности — [verification.md](verification.md).
