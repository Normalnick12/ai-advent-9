# Day 23 — Query rewrite и relevance filtering

## Суть эксперимента

CLI преобразует исходный вопрос в retrieval query через LLM, ищет Top-10
в сохранённом structure-aware индексе Day 21, применяет cosine threshold 0.50
и оставляет максимум пять chunks. Generation отвечает на исходный вопрос.
Сравнение использует десять frozen questions, ответы и ручной review Day 22;
baseline повторно не запускается, generation model/instruction/settings прежние.

## Что проверяет

- Сохраняет ли rewrite смысл вопроса и помогает ли находить нужные факты.
- Что filter удаляет или сохраняет, включая пустой context и регрессии.
- Per-fact coverage context/answer относительно Day 22 и groundedness нового ответа.

## Результаты

2 октября 2026 выполнены один `retrieve` и один `compare`: 10 rewrites,
10 query embeddings и 10 enhanced answers технически завершены без повторов.
Ручной review подтвердил сохранение intent всех rewrites и не нашёл добавленных project
assumptions; это не обеспечило улучшения retrieval fact coverage.

Q01–Q04, Q06 и Q09 сохранили полное coverage context/answer. Q05 регрессировал:
оба факта, найденные baseline, исчезли из final context и ответа. Нужный contract
попал в Top-10 на rank 6 с cosine 0.4309, но был отфильтрован; ответ честно признал
недостаток данных. Q07–Q08 сохранили retrieval gaps и неподдержанные переносы
правил между сценариями. В Q07 прямой Day 13 contract был candidate 7 выше
порога, но не прошёл maximum Top-5.

Q10 после rewrite сохранил два chunks со scores 0.5477/0.5178, хотя искомых
RPO/RTO в них нет. Ответ снова обозначил недостаток сведений. Порог остался 0.50;
cosine filter не гарантирует наличие знания даже у прошедшего candidate.

Threshold выбран по Day 22 evidence, включая Q10, на original queries;
rewrite изменил scores. Это один локальный эксперимент, не независимый benchmark:
cosine не вероятность релевантности, filtering не меняет ranking и может удалять
полезные chunks. Saved run: `facf8d92-bd1d-482f-bf6e-2585565f6904`.

Контракт — в [backend](../backend/README.md#day-23--query-rewrite-и-relevance-filtering),
команды — в [scripts](../scripts/README.md#day-23--query-rewrite-и-relevance-filtering).
`OPENAI_API_KEY` задаётся только в окружении backend; evidence хранится локально.
