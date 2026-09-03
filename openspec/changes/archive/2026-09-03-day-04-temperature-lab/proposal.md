## Why

Day 04 должен изолированно показать влияние `temperature` на соблюдение формальных требований и разнообразие ответов, не смешивая результат с изменением prompt, reasoning, output contract или других параметров. Для честного учебного сравнения нужны три сопоставимых вызова, независимый детерминированный validator и понятный русскоязычный экран без искусственных оценок креативности.

## What Changes

- Расширить существующий FastAPI backend отдельным Temperature Lab endpoint, который сравнивает один и тот же prompt при `temperature = 0`, `0.7` и `1.2` на `gpt-5.6`, фиксируя `reasoning.effort=none`, `max_output_tokens=600`, default `top_p` и остальные параметры.
- Первой implementation-задачей выполнить живой Responses API probe всей выбранной комбинации параметров для трёх temperature и явно остановить или скорректировать план при реальной несовместимости, а не обходить её молча.
- Для канонического benchmark использовать одинаковый strict Structured Output с массивом `variants` (`name`, `slogan`) без schema-ограничения ровно на пять элементов; независимо проверять пять формальных критериев и возвращать «Соблюдение требований: N/5».
- Для изменённого пользователем prompt включать свободный режим: передавать один и тот же текст всем трём вызовам без изменений, получать обычный text response и отключать benchmark-validator и подсчёт уникальных названий.
- Добавить в существующий Android app отдельный полностью русскоязычный экран Temperature Lab с редактируемым benchmark prompt, read-only параметрами, конкурентным запуском трёх вариантов, раскрываемыми ответами, метриками, session-only историей до трёх запусков текущего prompt и накопительной уникальностью benchmark-названий.
- Не добавлять editable controls из Day 02/03, LLM-as-a-judge, Creativity Score или автоматическую численную оценку семантической уместности и креативности; сохранить существующие Day 02/03 экраны и API.
- Во время apply создать `day-04-temperature-lab/README.md` с назначением, зависимостями, настройкой окружения, запуском и требуемыми переменными окружения.

## Capabilities

### New Capabilities

- `temperature-experiment`: сопоставимый backend-эксперимент с тремя temperature, двумя режимами ответа, независимой benchmark-валидацией, метриками и изоляцией частичных ошибок.
- `temperature-lab-android`: русскоязычный экран существующего Android-приложения для запуска эксперимента, просмотра результатов, session-only истории и накопительной уникальности benchmark-названий.

### Modified Capabilities

Нет: Temperature Lab добавляет отдельные endpoint и экран, не меняя требования существующих `reasoning-strategy-evaluation` и `reasoning-lab-android`.

## Impact

- Backend: новые transport-модели, endpoint и orchestration/service для Temperature Lab, strict JSON Schema benchmark-ответа, text path свободного режима, validator, нормализация, метрики и unit/API tests; существующие `/api/v1/generate` и `/api/v1/reasoning-lab/run` остаются совместимыми.
- Android: новые DTO/repository method, ViewModel/state и Compose screen, третья точка навигации, локальная история и агрегаты в памяти, а также unit/UI tests в текущем `app` module.
- OpenAI API: три Responses API вызова на один запуск; требуется реальный API key только на backend и обязательный compatibility probe до основной реализации.
- Документация: новый `day-04-temperature-lab/README.md`; реальные секреты не сохраняются.
