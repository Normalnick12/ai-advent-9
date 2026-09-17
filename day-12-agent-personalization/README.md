# Day 12 — Персонализация ассистента

## Суть эксперимента

Profile задаёт язык, тон, подробность, формат и поддерживаемые ограничения ответа.
Память сохраняет факты о проекте и текущей задаче. Это независимые durable состояния:
переключение Profile не создаёт conversation/task и не сбрасывает Memory.

Android позволяет создавать, редактировать и явно выбирать профили. Обычный Send
автоматически применяет active Profile. Controlled A/B сравнивает Compact Engineer
и Mentor с одним frozen memory/transcript, вопросом и настройками модели;
ответы probes не записываются в разговор.

## Что проверяет

- Create/edit/select, ownership, revisions и восстановление active binding.
- Независимость Profile от Short-term, Working и Long-term.
- Различие между selection, фактическими LlmClient instructions и соблюдением профиля моделью.
- Ограниченные Markdown/emoji checks отдельно от субъективной оценки тона и полезности.
- Отсутствие replay при чтении, rotation и восстановлении приложения.

## Результаты

В одном живом прогоне, подтверждённом пользователем, настоящий seed принят
без retry и редактирования: содержательно нейтральное подтверждение с лёгким
оформлением Compact. A/B выполнен на одном frozen Memory/transcript с одинаковыми
query/model/settings. Оба probes имели `committed=false`; ответ A не попал в input B.

| Profile | Selection | Assembly | Проверки ответа |
| --- | --- | --- | --- |
| Compact Engineer | pass | pass | summary и no_emoji — pass; list_limit — **FAIL: 8 пунктов при max 3** |
| Mentor | pass | pass | headings, nonempty_sections и no_emoji — pass |

Нарушение max_bullets у Compact — model-adherence failure: Profile и actual request
были корректными, но модель не соблюла ограничение. Прогон ради идеального
результата не повторялся; один прогон не доказывает устойчивую закономерность.

Обычные Send без style hints автоматически применяли Mentor, а после explicit
switch — Compact Engineer. Inspector подтверждал выбранный Profile; пользователь
не передавал его вручную в query.

После restart backend и открытия Day 12 read-only восстановились active Profile,
Profiles/revisions, Memory и owner/task/session state. По подтверждённому
пользователем результату восстановление не выполняло generation или replay.

Вывод: корректный выбор профиля и сборка запроса не гарантируют соблюдения всех
его требований моделью. Profile остаётся самостоятельным состоянием поверх Memory.

Зависимости, настройка и запуск описаны в [инструкции по запуску](../scripts/README.md).
`OPENAI_API_KEY` задаётся только на backend.
