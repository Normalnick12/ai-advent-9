## 1. Conversation storage

- [x] 1.1 Добавить минимальный ConversationStore contract create/load/append_turn/delete и нейтральный результат загрузки; проверить отсутствие SQL/SDK/HTTP types в contract и различение отсутствующей/пустой session тестом.
- [x] 1.2 Реализовать SQLiteConversationStore с sessions/messages, position PK, FK cascade и явным foreign_keys=ON; проверить создание/повторное открытие schema, исходные роли/Unicode/пробелы/переводы строк, пары и отклонение повреждённой history на реальном tmp_path SQLite.
- [x] 1.3 Ввести явные совместимые с Python 3.11+ BEGIN/COMMIT/ROLLBACK для create/append/delete без ORM/Alembic/WAL; проверить rollback между INSERT user/assistant, отсутствие половины turn после reopen и commit ошибки без ложного успеха.
- [x] 1.4 Организовать путь `.local/agent/conversations.sqlite3` от расположения проекта, constructor-injected test path и lifecycle connection; проверить независимость пути от cwd, закрытие connection и `git check-ignore` для DB/sidecars без создания пользовательской БД тестами.

## 2. Session lifecycle и неизменный Agent

- [x] 2.1 Подключить store к AgentSession/Manager: create публикует объект после записи, get лениво восстанавливает ID/full history в пустой mapping; проверить create/reopen пустой session, cache identity, lazy restore без preload и 404 неизвестного ID без автосоздания.
- [x] 2.2 Реализовать commit в порядке prepared snapshot -> durable pair -> RAM assignment, сохранив алгоритм SimpleAgent и освобождение busy в finally; проверить все неподходящие LLM outcomes/cancellation и storage failure без изменения RAM/count или completed ответа.
- [x] 2.3 Реализовать persistent delete до close/eviction, включая cache miss; проверить busy 409, stale reference rejection, delete unloaded session, повторный delete, rollback удаления и отсутствие session/messages после reopen.
- [x] 2.4 Добавить основной restart test: A сохраняет U1/A1 в реальный SQLite, закрывается и теряет все Store/Manager/Session references, B открывает тот же файл; проверить тот же ID/history и exact fake LLM input U1/A1/U2, а также isolation нескольких sessions и сброс runtime busy после reopen без обязательного OS child-process crash test.
- [x] 2.5 Подключить один SQLite-backed manager в FastAPI lifespan и корректное освобождение store/SDK client, включая startup failure; проверить пустой startup mapping, отсутствие RAM-only fallback и lifecycle tests без ключа, не меняя services Day 02–05.

## 3. HTTP contract

- [x] 3.1 Добавить metadata GET с существующим SessionResponse ID/count, safe 404/409/422/500 и X-Request-ID; проверить точный набор полей, восстановленную/пустую/busy session, отсутствие history/config, create и LLM-вызовов, работу без OPENAI_API_KEY.
- [x] 3.2 Обновить текст session_not_found без утверждения о потере при обычном restart; проверить безопасные create/append/delete storage errors и отсутствие success до commit в API tests, не меняя strict bodies и остальные turn DTO.
- [x] 3.3 Изолировать lifespan/API fixtures через tmp_path DB до их запуска и адаптировать только прежнее volatile restart ожидание; проверить backend pytest и точные прежние context/config/SDK payload/retry/error contracts Day 02–06, не открывая `.local` application DB.

## 4. Android identity и восстановление

- [x] 4.1 Добавить CurrentSessionStore и private SharedPreferences implementation для одного nullable Day 07 sessionId через AppContainer/application context; проверить IO dispatcher, обработку read/save/clear failure и реальный round-trip/clear между экземплярами store instrumented тестом на отдельном preferences file.
- [x] 4.2 Добавить GET в ChatApi/Repository с проверкой совпадающего ID и count >= 0; проверить Retrofit interceptor-тестом точные GET/POST/DELETE, safe errors и message body только с новым message, без history и retries.
- [x] 4.3 Добавить Day 07 sequence create -> confirmed local save -> send и runtime guard неподтверждённого ID; проверить порядок fake calls, draft при save failure, явный retry save без повторного create и отсутствие send до успешной записи ID.
- [x] 4.4 Добавить однократную инициализацию Day 07 при входе, read-ID/RESTORING/GET/ready и явный retry; проверить cold start без ID без HTTP, restore того же ID/count без create/replay/transcript, блокировку send до metadata и обработку local read/GET/404/409 ошибок.
- [x] 4.5 Реализовать Day 07 reset DELETE 204 -> confirmed local clear -> UI reset; проверить порядок, delete/clear failure без ложной очистки UI, идемпотентный повтор и отсутствие сохранённого ID после подтверждённого reset/cold start.
- [x] 4.6 Сохранить known-failure retry и unknown-send recoveryRequired в текущем процессе, не persistить pending/outcome markers; проверить старые ViewModel regression tests, отсутствие auto replay и count previous+1 после restore с пустыми bubbles.

## 5. Отдельная лаборатория Day 07 на общих компонентах

- [x] 5.1 Переиспользовать ChatScreen/ChatViewModel с двумя keyed activity-scoped состояниями и CurrentSessionStore только у Day 07; проверить независимость ID/draft/transcript/operations/reset двух дней и отсутствие второго backend Agent stack.
- [x] 5.2 Добавить шестую карточку/destination «День 07 — Сохранение контекста», параметризовать общий chat header и сохранить root navigation; проверить порядок шести карточек, отдельные заголовки и отсутствие create/send/restore при простом открытии каталога.
- [x] 5.3 Добавить русские restore/loading/error/retry/confirmed сообщения и корректный count без старого transcript; проверить Compose tests пустого/восстановленного/ошибочного состояния, переносы длинного текста и доступность ввода/действий над IME, без controls для внутренних history/settings.
- [x] 5.4 Расширить navigation/Activity recreation tests: уход/возврат/rotation не повторяют GET/POST/DELETE и не отменяют операции, scroll и состояние Day 02–07 независимы; подтвердить полный UI suite после всех связанных изменений через scripts/dev.ps1.

## 6. Документация, интеграция и live restart

- [x] 6.1 Создать `day-07-context-persistence/README.md` по разделам «Суть эксперимента», «Что проверяет», «Результаты», со ссылками на общие компоненты; обновить backend/Android README и при необходимости scripts README, уточнить исторический Day 06 README без переписывания его результатов; проверить ссылки и отсутствие неподтверждённых итогов/секретов.
- [x] 6.2 Выполнить итоговые backend pytest, Android unit/build и необходимые UI checks через PowerShell 7 scripts/dev.ps1 с переиспользованием актуальных успешных результатов; проверить отсутствие регрессий Day 02–06 кроме явно изменённого persistence lifecycle и зафиксировать фактические итоги.
- [x] 6.3 Отдельно подготовить живое окружение: управляемая backend terminal session через scripts/dev.ps1 backend, status, работающий эмулятор и доступность backend с него; проверить готовность без подмены проверки OpenAI ответом /health.
- [x] 6.4 Выполнить или получить подтверждение live/video: выдуманный факт -> completed/count 1 -> полная остановка backend -> force-stop Android без clear data -> запуск backend/Android -> открытие Day 07 и restore/count 1 -> явный вопрос о факте -> фактический ответ/count 2; записать только проверенный результат, без автоматического replay/платных повторов и без crash внутри неопределённого turn.
- [x] 6.5 Сверить реализацию с уже синхронизированными target specs и архивом Day 06, выполнить strict validation change/актуальных specs, git diff --check/status и проверку состава файлов; подтвердить отсутствие DB/sidecars/секретов и непрошеных frameworks, не выполнять commit/push/archive без отдельного запроса.
