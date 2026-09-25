# Day 20 — пояснения к review единственной попытки

Attempt: `329e8e15-ce73-4c14-9a89-4cf4b1f56e1a`.
Provider response: `resp_0e5536fbc312b329016ab67e3c8d3c87d2ba14c7d4d103943f`, status `completed`.
Выполнена одна отправка; дополнительных model/MCP calls после неё нет.

Основной результат — [report.md](report.md), исходный verdict — [verdict.json](verdict.json).
Они не изменены. Эти пояснения получены только чтением сохранённых данных.

## Что подтверждено

Один request одновременно зарегистрировал DeepWiki (три импортированных tools)
и Dependency Composition (только lookup и summary); tool_choice=auto, retries=0.
Модель выбрала ask_wiki_question дважды с разными вопросами: сначала поиск
артефактов и версий, затем уточнение дословных catalog/module lines и revision.
Затем выполнены Room lookup → Room summary → WorkManager lookup → WorkManager summary.

- androidx.room:room-runtime — found, 92 публикации, последние: 2.8.3, 2.8.4, 2.8.5.
- androidx.work:work-runtime-ktx — found, 91 публикация, последние: 2.12.0-beta01, 2.12.0-rc01, 2.12.0.

Обе полные передачи lookup → summary, count/last_three/hash и наблюдаемый DAG
прошли независимую проверку. Ошибочных tool calls нет.
Flow PASS; final_facts PASS относится только к двум ролям/идентификаторам
и publication facts, а не ко всем утверждениям исходного ответа.

## Все FAIL / NOT_PROVEN

Для обеих веток repository_claim.provenance = FAIL.
Verifier выбрал первый research output, содержащий полные coordinates.
Модель в final ссылается на второй research output и объединяет несколько
раздельных строк в repository_excerpt. Проверка по raw evidence установила:

- Каждая отдельная строка обеих final excerpts присутствует во втором output.
- Ссылка source_url присутствует во втором output, но не в первом.
- Объединённый final excerpt не встречается цельной подстрокой ни в одном output.
- Final excerpt содержит TOML group/name, но не буквальную строку group:artifact.

Это объясняет FAIL точной проверки provenance и не является доказательством
выдуманных строк. Исходный verifier не изменялся, его verdict не переопределён.

Для обеих веток declared_publication = NOT_PROVEN: verifier не выполняет
проверку членства объявленных 2.8.3 / 2.10.0 после провала provenance gate.
Это не утверждение об отсутствии версий в Maven.

source_truth = NOT_PROVEN: DeepWiki output не устанавливает независимо истину
исходников, семантические роли и актуальность revision. Во втором ответе прямо
указано отсутствие GitHub file URLs и commit SHAs; final revision=null.
Отчёт не доказывает физический порядок на серверах или внутреннюю причинность
выбора модели. Вывод ограничен одной сохранённой попыткой.

Task 6.3, видео и finish не выполнялись.
