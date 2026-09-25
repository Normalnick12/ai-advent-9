# Day 20 — наблюдаемый developer-flow

> Отчёт приложения по сохранённому evidence. Не новый ответ модели.

## Инженерная задача

Исследуй в android/nowinandroid зависимости для локального хранения данных и фоновой работы/синхронизации. Для каждой задачи выбери один конкретный используемый Maven-артефакт, укажи роль, координаты, объявленную версию и доступные ссылки на исходники/ревизию. Проверь публикации в Google Maven и получи средствами доступных инструментов отдельную сводку: статус, количество и три последних элемента в порядке источника. Не делай выводов о совместимости или рекомендации обновления; неизвестное обозначь явно.

## Переход между системами

Исследование repository нужно для выбора зависимостей; Google Maven — для проверки публикаций.
Ниже фактические calls; объяснение назначения не является скрытым рассуждением модели.

1. deepwiki / ask_wiki_question — mcp_0e5536fbc312b329016ab67e43446887d29313c98ead4ef1fc (events: 10 → 14)
2. deepwiki / ask_wiki_question — mcp_0e5536fbc312b329016ab67e50575087d2b076c6576e68d484 (events: 16 → 20)
3. dependency_composition / get_google_maven_versions — mcp_0e5536fbc312b329016ab67e59c5b087d295239c937ced8209 (events: 22 → 26)
4. dependency_composition / summarize_dependency_versions — mcp_0e5536fbc312b329016ab67e61a91887d2bf985d5349194480 (events: 28 → 32)
5. dependency_composition / get_google_maven_versions — mcp_0e5536fbc312b329016ab67e63520087d293a3fe75d84ab2d9 (events: 34 → 38)
6. dependency_composition / summarize_dependency_versions — mcp_0e5536fbc312b329016ab67e6a2d8087d2950679b926ddb242 (events: 40 → 44)

Calls упорядочены по наблюдаемому началу; без start event показаны в конце. Номера events отсчитываются от нуля. Завершение и зависимости проверены отдельно.

- PASS: mcp_0e5536fbc312b329016ab67e43446887d29313c98ead4ef1fc
- PASS: mcp_0e5536fbc312b329016ab67e50575087d2b076c6576e68d484
- PASS: mcp_0e5536fbc312b329016ab67e59c5b087d295239c937ced8209
- PASS: mcp_0e5536fbc312b329016ab67e61a91887d2bf985d5349194480
- PASS: mcp_0e5536fbc312b329016ab67e63520087d293a3fe75d84ab2d9
- PASS: mcp_0e5536fbc312b329016ab67e6a2d8087d2950679b926ddb242

## Инженерный результат

| Роль по ответу модели | Координаты | Статус Maven | Количество |
|---|---|---|---|
| local_storage | androidx.room:room-runtime | found | 92 |
| background_work | androidx.work:work-runtime-ktx | found | 91 |

Это сводка сохранённых публикаций, не рекомендация обновления.

## Две dependency-ветки

### androidx.room:room-runtime

Research: mcp_0e5536fbc312b329016ab67e43446887d29313c98ead4ef1fc; lookup: mcp_0e5536fbc312b329016ab67e59c5b087d295239c937ced8209; summary: mcp_0e5536fbc312b329016ab67e61a91887d2bf985d5349194480.

Наблюдавшийся фрагмент research:

> The Now in Android project uses `androidx.room:room-runtime` for local data storage and `androidx.work:work-runtime-ktx` for background work/synchronization. Both artifacts are defined in the `gradle/libs.versions.toml` file, which acts as a version catalog for the project's dependencies .
> 
> ## Loca

Публикации: found; количество: 92; последние элементы: 2.8.3, 2.8.4, 2.8.5.

Роль по ответу модели: local_storage. Объявленная версия: 2.8.3.
Объяснение модели: Цитаты наблюдались в исследовании DeepWiki: объявление версии и координат — в gradle/libs.versions.toml, использование алиаса — в build-logic/convention/src/main/kotlin/AndroidRoomConventionPlugin.kt. Точная ревизия и GitHub URL индексом не предоставлены. Публикации проверены по https://dl.google.com/dl/android/maven2/androidx/room/group-index.xml; три элемента сохранены в порядке источника..
Источник: https://deepwiki.com/search/return-verbatim-lines-not-para_842f0ac8-e6dd-453d-94e2-6d5cade94ae3; revision: None.
Происхождение цитаты/ссылки в research: FAIL.
Членство объявленной версии в полученных публикациях: NOT_PROVEN; published=None.
Использование этой версии в исходниках независимо не подтверждено.

- distinct_dependency: **PASS** — coordinate used once
- research_to_lookup: **PASS** — explicit coordinate in raw research
- research_order: **PASS** — observed Responses runtime dependency order
- lookup_to_summary: **PASS** — full result of this lookup
- summary_order: **PASS** — observed Responses runtime dependency order
- summary_facts: **PASS** — independent count/last_three/hash

### androidx.work:work-runtime-ktx

Research: mcp_0e5536fbc312b329016ab67e43446887d29313c98ead4ef1fc; lookup: mcp_0e5536fbc312b329016ab67e63520087d293a3fe75d84ab2d9; summary: mcp_0e5536fbc312b329016ab67e6a2d8087d2950679b926ddb242.

Наблюдавшийся фрагмент research:

> The Now in Android project uses `androidx.room:room-runtime` for local data storage and `androidx.work:work-runtime-ktx` for background work/synchronization. Both artifacts are defined in the `gradle/libs.versions.toml` file, which acts as a version catalog for the project's dependencies .
> 
> ## Local Data Storage Artifact
> 
> The Maven artifact used for local d

Публикации: found; количество: 91; последние элементы: 2.12.0-beta01, 2.12.0-rc01, 2.12.0.

Роль по ответу модели: background_work. Объявленная версия: 2.10.0.
Объяснение модели: Цитаты наблюдались в исследовании DeepWiki: объявление версии и координат — в gradle/libs.versions.toml, использование алиаса — в sync/work/build.gradle.kts. Точная ревизия и GitHub URL индексом не предоставлены. Публикации проверены по https://dl.google.com/dl/android/maven2/androidx/work/group-index.xml; три элемента сохранены в порядке источника..
Источник: https://deepwiki.com/search/return-verbatim-lines-not-para_842f0ac8-e6dd-453d-94e2-6d5cade94ae3; revision: None.
Происхождение цитаты/ссылки в research: FAIL.
Членство объявленной версии в полученных публикациях: NOT_PROVEN; published=None.
Использование этой версии в исходниках независимо не подтверждено.

- distinct_dependency: **PASS** — coordinate used once
- research_to_lookup: **PASS** — explicit coordinate in raw research
- research_order: **PASS** — observed Responses runtime dependency order
- lookup_to_summary: **PASS** — full result of this lookup
- summary_order: **PASS** — observed Responses runtime dependency order
- summary_facts: **PASS** — independent count/last_three/hash

## Независимая проверка

Наблюдаемый flow: **PASS**.
Финальные факты модели: **PASS** — two roles and publication facts match; repository truth not assessed.

- registration: PASS — two independent descriptors, allowlists and auto
- import_deepwiki: PASS — native tool definitions
- import_dependency_composition: PASS — native tool definitions
- execution: PASS — all observed calls checked
- both_servers_called: PASS — actual server labels
- two_branches: PASS — two lookups and two summaries; extras remain visible
- evidence: PASS — available records read

## Исходный ответ модели

{"branches":[{"role":"local_storage","group_id":"androidx.room","artifact_id":"room-runtime","declared_version":"2.8.3","repository_excerpt":"room = \"2.8.3\"\nroom-runtime = { group = \"androidx.room\", name = \"room-runtime\", version.ref = \"room\" }\n\"implementation\"(libs.findLibrary(\"room.runtime\").get())","source_url":"https://deepwiki.com/search/return-verbatim-lines-not-para_842f0ac8-e6dd-453d-94e2-6d5cade94ae3","revision":null,"lookup_id":"e4fedc19-cc9f-4468-9fb9-9cff285c8d5c","status":"found","version_count":92,"last_three":["2.8.3","2.8.4","2.8.5"],"explanation":"Цитаты наблюдались в исследовании DeepWiki: объявление версии и координат — в gradle/libs.versions.toml, использование алиаса — в build-logic/convention/src/main/kotlin/AndroidRoomConventionPlugin.kt. Точная ревизия и GitHub URL индексом не предоставлены. Публикации проверены по https://dl.google.com/dl/android/maven2/androidx/room/group-index.xml; три элемента сохранены в порядке источника."},{"role":"background_work","group_id":"androidx.work","artifact_id":"work-runtime-ktx","declared_version":"2.10.0","repository_excerpt":"androidxWork = \"2.10.0\"\nandroidx-work-ktx = { group = \"androidx.work\", name = \"work-runtime-ktx\", version.ref = \"androidxWork\" }\nimplementation(libs.androidx.work.ktx)","source_url":"https://deepwiki.com/search/return-verbatim-lines-not-para_842f0ac8-e6dd-453d-94e2-6d5cade94ae3","revision":null,"lookup_id":"50298fcd-ceda-41e5-8b36-c71e5aab92a7","status":"found","version_count":91,"last_three":["2.12.0-beta01","2.12.0-rc01","2.12.0"],"explanation":"Цитаты наблюдались в исследовании DeepWiki: объявление версии и координат — в gradle/libs.versions.toml, использование алиаса — в sync/work/build.gradle.kts. Точная ревизия и GitHub URL индексом не предоставлены. Публикации проверены по https://dl.google.com/dl/android/maven2/androidx/work/group-index.xml; три элемента сохранены в порядке источника."}],"conclusion":"В исследованном состоянии android/nowinandroid для локального хранения используется androidx.room:room-runtime:2.8.3, а для фоновой работы и синхронизации — androidx.work:work-runtime-ktx:2.10.0. Оба артефакта найдены в Google Maven; точная ревизия исследованного репозитория неизвестна, поэтому принадлежность сведений актуальному main не утверждается."}

## Ограничения

Repository truth/revision и смысловая роль зависимости: NOT_PROVEN.
Цитата подтверждает наблюдавшиеся данные, но не их истинность и не источник внутренних знаний модели.
Порядок относится к Responses runtime, не серверным журналам. Публикация не означает совместимость, безопасность или latest/stable.
Это одна попытка. Дополнительные calls не удалены. Отчёт сохранён локально приложением, не MCP save.
