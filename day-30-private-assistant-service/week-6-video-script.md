# Week 6 — сценарий скринкаста без озвучки

Продолжительность около 2 минут 40 секунд. Пользователь записывает самостоятельно;
видео не является условием Git-финализации. Это обзор существующего кода и
сохранённых результатов. Новая live-демонстрация модели не проводится.

Перед записью откройте только файлы ниже и терминал в корне проекта. Увеличьте
шрифт, закройте панели с личными данными. Не показывайте `.local`, DPAPI, переменные
с токенами, конфигурацию с секретами или историю терминала. Достаточно просмотра
файлов редактором; сервер и Tailscale включать не нужно.

| Время | Что показать | Короткая надпись на экране |
|---|---|---|
| 0:00–0:15 | Корневой `README.md`, ссылки Days 26–30 | «Week 6: от локальной модели до приватного сервиса» |
| 0:15–0:30 | `day-26-local-llm/README.md`, подтверждённые результаты | «Ollama + Qwen на Windows. Первые Kotlin-запросы» |
| 0:30–0:50 | `day-27-local-architecture-assistant/tests/fixtures/CheckoutCoordinator.kt`, затем Day 27 README, раздел результатов | «Один разрешённый файл. Структура и ссылки проверяются. Смысл: PARTIAL» |
| 0:50–1:10 | `day-28-local-architecture-rag/fixtures/knowledge/checkout.md` и Day 28 README | «Markdown → SQLite → поиск → контекст. Улучшение качества A/B не подтверждено» |
| 1:10–1:30 | `day-29-local-assistant-optimization/README.md`, начало результатов | «Qwen3 4B / Coder 7B. Подходящий профиль не подтверждён» |
| 1:30–1:55 | `day-30-private-assistant-service/laa_service/README.md`, HTTP-контракт; затем `week-6-technical.md`, таблица проверок | «HTTP необязателен. Bearer auth, лимиты, два клиента. 415 passed / 1 skipped» |
| 1:55–2:20 | `openspec/changes/day-30-private-assistant-service/live-remote-2026-10-11.md`, итог приёмки и cleanup | «Android HTTPS + auth: PASS. Доставка второго chat-ответа не подтверждена» |
| 2:20–2:40 | Безопасные Git-команды ниже и таблица итогов Week 6 | «5 отдельных коммитов. Ограничения сохранены. Serve выключен, токен отозван» |

Команды только для просмотра; ни одна не запускает модель и не меняет инфраструктуру:

```powershell
git log --reverse --oneline 69c1495..HEAD
git status --short --branch
git diff --stat 69c1495..HEAD
```

Если удобнее показывать текст в терминале:

```powershell
Get-Content -LiteralPath day-26-local-llm/README.md
Get-Content -LiteralPath day-30-private-assistant-service/README.md
Get-Content -LiteralPath day-30-private-assistant-service/week-6-technical.md
```

Не выдавайте просмотр отчёта за новый запрос с телефона. Отдельно подчеркните:
обе финальные внутренние генерации завершились, Windows получил 200, но Android
не подтвердил получение ответа. Бюджет 8/8 исчерпан. Финальная карточка:
«Реализовано и принято с известным ограничением; качество модели не подтверждено».
