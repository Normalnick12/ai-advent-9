## 1. CLI, снимок PR и ограниченный RAG

- [x] 1.1 Создать небольшой `backend/app/pr_review/` и CLI `backend/scripts/day32_review.py`; реализовать REST snapshot, pinned base/head/merge-base revisions и лимиты из design. Проверить CLI help и fixtures полного/неполного diff, rename/delete, смены SHA и превышения лимитов; PR-код не исполняется.
- [x] 1.2 Подключить существующие chunking/embeddings/cosine search: пять документов Day 31, изменённые `.py`/`.kt` и не более двух очевидных тестов на файл, два индекса в памяти. Fake-embedding тест подтверждает отдельный retrieval docs/code, path/revision/lines и отсутствие recursive imports, БД и записи PR-файлов в runtime checkout.
- [x] 1.3 Добавить один Responses request, input count и строгий findings contract с Python validation/Markdown. Fake-LLM проверки покрывают valid/empty findings, неизвестные IDs, неверные changed-line anchors, incomplete/error и отсутствие retries; локальный запуск не публикует комментарий.

## 2. Автоматизация, публикация и offline readiness

- [x] 2.1 Добавить signal `pull_request` и trusted `workflow_run` workflows с main checkout, закреплёнными Actions, Environment, минимальными permissions и per-PR concurrency. Проверить YAML и event-gate fixtures: fork/Dependabot/подмена workflow/неоднозначный PR не доходят до OpenAI; PR code, dependencies и artifacts никогда не запускаются/загружаются в trusted job.
- [x] 2.2 Реализовать один bot comment и краткий Summary, проверку SHA до публикации и защиту от позднего старого run. Fake-GitHub сценарии подтверждают обновление того же comment ID, сохранность чужого/нового comment, явные error/stale statuses и отсутствие inline comments/approve/merge.
- [x] 2.3 Добавить Day README и ссылку на него в «Задания» корневого README, инструкции в backend/scripts README, включая Environment setup и ограничения. Проверить существование ссылок и отсутствие непроверенных результатов/секретов; пока отметить live как не проведённый.
- [x] 2.4 Выполнить новые Day 32 tests и целевую регрессию из design, `pip check`, syntax/YAML checks. Записать фактический итог; повторять только затронутые проверки после изменений, Android/полный backend suite без причины не запускать.

## 3. Bootstrap и настоящий PR — после отдельного разрешения

- [x] 3.1 После успешного offline review и явного разрешения пользователя выполнить bootstrap commit/push доверенной реализации в `main` по AGENTS.md. Проверить отсутствие секретов/demo defects в commit, совпадение local/remote SHA и наличие обоих workflows; Day 32 пока не финализировать.
- [x] 3.2 Пользователь настраивает GitHub UI: Environment `day32-review`, только Branch `main`, без required reviewers/wait timer, Environment secret `OPENAI_API_KEY`. Read-only сверкой проверить фактическую branch policy и имя secret без вывода значения; зафиксировать, что PR refs не разрешены и repository secret не дублируется.
- [x] 3.3 После разрешения на demo PR создать `codex/day32-review-demo` с двумя дефектами из design и открыть PR в `main`. Дождаться настоящей автоматической цепочки; проверить Linux install, trusted reviewer SHA, Environment access, получение diff и sources, комментарий и Summary. Зафиксировать PR/run URL и вручную подтвердить оба дефекта и корректность оснований. Принято пользователем: обнаружение 2/2 PASS, объяснение B PARTIAL; оговорки сохранены в validation.md.
- [x] 3.4 Отправить исправляющий commit в тот же PR, сохранив небольшой безвредный diff. Дождаться автоматического повторного запуска; подтвердить новый head SHA, тот же comment ID, отсутствие утверждений об исправленных дефектах и вручную оценить остальные findings. Зафиксировать второй run URL; demo defects не сливать. PASS: head `3a59e5e`, runs `38956137731`/`38956152557`, comment `6223009917` обновлён, findings=0; scope и usage — в validation.md.

## 4. Видео и передача к завершению дня

- [x] 4.1 Пользователь записывает короткое видео по design: PR diff → Actions → findings/источники → исправление → обновлённый comment. Получить подтверждение записи, не выдавать replay за новый live-run; отметить реальные ограничения и неуспешные проверки, если они были. Пользователь подтвердил запись немого скринкаста; агент файл не просматривал, видео хранится вне Git.
- [x] 4.2 Обновить Day README только фактическими результатами и сохранить краткие PR/run/SHA/comment references в planning-документации; проверить корневую ссылку и отсутствие секретов. После разрешения закрыть demo PR без merge, убедиться, что дефекты отсутствуют в `main`; финальные archive/commit/push выполнять только по отдельному запросу завершения Day 32. PR #1 CLOSED, mergedAt=null, 2026-10-16T19:50:48Z; main без дефектов. Отдельное разрешение на финализацию получено.
