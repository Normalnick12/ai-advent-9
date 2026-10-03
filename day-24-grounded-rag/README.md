# Day 24 — Проверяемые RAG-ответы

## Суть эксперимента

CLI повторяет original-query Top-5 из сохранённых Day 22 query vectors и индекса
Day 21. Меняется контракт ответа: модель возвращает answer, sources и точные
citations, а runtime проверяет ссылки и наличие цитат в переданных chunks.
Если лучший cosine ниже 0.50, программа отвечает «не знаю / уточните» без
generation. При PASS передаются все пять chunks, включая chunks ниже порога.

## Что проверяет

- Проверяемость source/section/chunk_id и дословность цитат; schema сама по себе
  не доказывает корректность provenance или поддержку ответа.
- Отдельную ручную оценку смысловой поддержки answer цитатами, неподдержанных
  утверждений и expected-fact correctness/coverage.
- Различие runtime abstention без call, model abstention после PASS и technical
  failure. У корректного insufficient_context sources/citations пусты.

## Результаты

3 октября 2026 выполнен один frozen eval Q01–Q10: 9 generation calls, 0 новых
embeddings/rewrite. Q10 с best score 0.494346 остановлен gate без generation,
вернул deterministic «не знаю / уточните» с пустыми sources/citations. Model
abstention в этом run не наблюдался. Повторов и repair не было.

Q01–Q08 прошли deterministic validation. Ручной разбор сохранённых текстов
подтвердил полную поддержку цитатами у Q02–Q05, частичную у Q01/Q06/Q07 и отсутствие
поддержки заданного Send-сценария у Q08: настоящие цитаты описывали workflow event.
В Q01 часть правильных деталей не процитирована; Q06 обобщил частный count 1→2;
Q07 вывел поведение Send из наличия отдельных UI controls. Q05 сохранил полезный
rank-5 chunk ниже 0.50 и ответил с точной поддерживающей цитатой.

Q09 отвергнут: первая quote содержит 412 символов и склеивает фрагменты через
пропущенное предложение. Raw answer по смыслу согласуется с источниками, но
`validation_failed` сохранён, normalized result отсутствует. Это показывает,
почему literal exactness и semantic support проверяются отдельно.

Frozen replay всех вопросов совпал с Day 22; 78 offline-тестов Days 22–24 прошли.
Run `25cd12b1-7423-4f3a-bc68-1c017f599504` и review хранятся локально. Semantic
labels получены ручным разбором Codex, без отдельного judge-вызова; это не
независимая человеческая оценка.

Frozen vectors изолируют answer contract. Порог уже связан с теми же вопросами;
этот run не является независимым retrieval benchmark и не доказывает
универсальность threshold или semantic support по одному факту exact quote.

Контракт и evidence — в [backend](../backend/README.md#day-24--проверяемые-rag-ответы),
настройка, запуск и просмотр видео — в [scripts](../scripts/README.md#day-24--проверяемые-rag-ответы).
`OPENAI_API_KEY` задаётся только в окружении backend.
