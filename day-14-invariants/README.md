# Day 14 — Инварианты и ограничения состояния

## Суть эксперимента

Агент предлагает retry загрузки Checkout при неизменных Memory, Profile и Task State.
Отдельная policy задачи требует MVI, Compose, CoroutinesFlow и подтверждение оплаты.
Один запрос совместим с правилами, другой явно требует MVVM, RxJava и отключения
подтверждения. Подсказка модели помогает соблюдать ограничения, а принятие результата
решает детерминированная проверка typed proposal до сохранения ответа.

## Что проверяет

- Совместимое предложение может стать ответом только после всех обязательных проверок.
- Известный конфликт даёт безопасный отказ; raw нарушающий candidate не входит в историю.
- Технический сбой остаётся ошибкой операции и не создаёт пару user/refusal.
- New Conversation сохраняет policy задачи, а New Task требует новой подготовки.

## Результаты

Offline-проверки подтвердили accepted path с одним fake provider call, request conflict
с нулём вызовов и отказ при нарушающем candidate. Проверены rollback, неопределённый
результат записи и восстановление без повтора операции. Android показывает отдельно
decision, dispatch, commit и исторический receipt.

В единственном live-прогоне 17.09.2026 модель gpt-4o-mini вернула совместимый
candidate с bounded_backoff: MVI, Compose, CoroutinesFlow и обязательное
подтверждение оплаты. Все четыре проверки пройдены, trusted answer сохранён.
Actual payload совпал с заранее разрешённым; выполнен ровно один generation call.
Controlled conflict выявил три нарушения и сохранил deterministic refusal без
provider call. В истории две пары; State, Working, Long-term, Profile и policy
сохранены без изменений. Retry/regeneration/repair не выполнялись. Это наблюдение
одного прогона, а не гарантия поведения модели во всех запросах.

Гарантия ограничена проверяемыми typed decisions и trusted renderer: произвольный
код или естественный текст этим опытом не верифицируются.

Зависимости, настройка и запуск описаны в [backend](../backend/README.md)
и [Android](../android-app/README.md). `OPENAI_API_KEY` задаётся только на backend.
