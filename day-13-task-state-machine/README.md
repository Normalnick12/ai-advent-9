# Day 13 — Состояние задачи

## Суть эксперимента

Добавлена конечная машина состояний задачи: planning → execution → validation → done.
Working Memory хранит факты задачи, Profile — способ ответа, а Task State — этап,
шаг и ожидаемое действие. Переходы выполняются только явными событиями приложения;
LLM получает состояние в запросе, но не управляет им.

Pause сохраняет положение задачи. Во время паузы можно разговаривать с агентом,
но для продолжения workflow требуется отдельный Resume.

## Что проверяет

- Допустимые переходы, Pause/Resume на каждом незавершённом этапе и сохранение State в SQLite.
- Независимость State от смены conversation, Profile и остальных слоёв памяти.
- Влияние State на actual request при одинаковых Memory, Profile и вопросе.
- Продолжение после двух New Conversation: первая исключает execution transcript,
  вторая — последующий status transcript. Постановка остаётся в Working Memory.

## Результаты

Детерминированные backend-проверки подтвердили переходы, CAS/revision, rollback,
восстановление после reopen и отсутствие вызовов provider для FSM operations.
Recording-client подтвердил различие только State section и отсутствие старых
диалогов в финальном запросе. Android проверки покрыли controls, paused composer,
recovery, inspector, rotation и навигацию.

В отдельном live-прогоне 16 сентября 2026 выполнены ровно три запроса: execution,
status и continuation. Все ответы завершились, обе старые conversations были
исключены из continuation input. Модель правильно назвала PAUSED и сохранила MVI
и loading/error/success после Resume, но финальный ответ дал общие шаги и встречный
вопрос вместо конкретного продолжения реализации. Это частичное следование State,
а не ошибка FSM. Пользователь подтвердил оценку: «Частичное adherence: продолжение слабое». Ответы не
меняли State. Переход в validation выполнен отдельным IMPLEMENTATION_READY.

Зависимости, настройка и запуск описаны в [backend](../backend/README.md#day-13-task-state-machine)
и [Android](../android-app/README.md#day-13-task-state-machine). `OPENAI_API_KEY` задаётся только на backend.
