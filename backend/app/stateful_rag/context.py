import json
from dataclasses import replace

from app.grounded_rag.core import CONFIG as GROUNDED_CONFIG, messages as grounded_messages
from app.llm_client import ConversationMessage
from .models import CombinedResponse, TaskMemory

VERSION = 'day25-chat-v1'
CONFIG = replace(GROUNDED_CONFIG, version=VERSION, instructions=(
    GROUNDED_CONFIG.instructions +
    ' Day 25: верни два payload: grounded (ответ по правилам выше) и memory_update (changes). '
    'Исходный вопрос находится в question. recent_history — последние 3 пары разговора; '
    'task_memory — пользовательские условия задачи. Только rag_context доказывает факты проекта. '
    'История и память не являются доказательством project knowledge. Учитывай ранние условия '
    'и разрешай ссылки текущего вопроса через history/memory, но не пересказывай всю память каждый раз. '
    'memory_update предлагает ТОЛЬКО явные условия из текущего question: goal, constraints, '
    'terms, clarifications. Не извлекай факты из retrieved context, прежнего assistant/user или '
    'из собственного ответа. Не сохраняй вопросы, гипотезы, summary, project knowledge и заметки. '
    'quote — короткий буквальный фрагмент текущего question без изменения символов. '
    'set с item_id=null добавляет новый item; изменение/удаление требует существующий item_id '
    'из соответствующего поля. Для goal при его наличии указывай ID. action=remove только '
    'при явной отмене пользователем, quote цитирует отмену. Не предлагай две операции над одним item. '
    'ID/turn/offsets назначает runtime: не возвращай их в patch. Не обновляй уже известные условия '
    'из-за простой повторной формулировки вопроса. Если новых явных условий нет, changes=[]. '
    'Максимум: goal 512 символов; 6 constraints, 4 terms, 6 clarifications по 256 символов. '
    'При grounded.status=insufficient_context верни changes=[].'
), text_format={'type': 'json_schema', 'name': 'day25_combined', 'strict': True,
                'schema': CombinedResponse.model_json_schema()})


def retrieval_query(question, memory, recent):
    parts = [dict(layer='CURRENT', text=question, item_id=None)]
    seen = {question}
    for field, items in TaskMemory.model_validate(memory).groups():
        for item in sorted(items, key=lambda x: x.id):
            if item.text not in seen:
                parts.append(dict(layer=field.upper(), text=item.text, item_id=item.id))
                seen.add(item.text)
    previous = next((m['content'][:512] for m in reversed(recent) if m['role'] == 'user'), None)
    if previous and previous not in seen:
        parts.append(dict(layer='PREVIOUS_USER', text=previous, item_id=None))
    return parts, '\n'.join(f"{p['layer']}: {p['text']}" for p in parts)


def generation_context(question, memory, recent, hits):
    # Reuse Day 24 authoritative block formatting and five-distinct-chunks guard.
    blocks = json.loads(grounded_messages(question, hits)[0].content)['context']
    payload = dict(question=question, recent_history=recent, task_memory=memory, rag_context=blocks)
    return (ConversationMessage('user', json.dumps(payload, ensure_ascii=False)),), payload
