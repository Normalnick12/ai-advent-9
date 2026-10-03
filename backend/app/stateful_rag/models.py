"""Strict transport and extractive memory contracts; runtime owns provenance."""
from typing import Literal

from pydantic import Field, model_validator

from app.grounded_rag.core import GroundedResponse, StrictModel
from app.context_strategies_models import strict_json


class ChatError(Exception):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


class Item(StrictModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=512)
    source_user_turn: int = Field(ge=1)
    source_start: int = Field(ge=0)
    source_end: int = Field(gt=0)


class TaskMemory(StrictModel):
    goal: Item | None = None
    constraints: list[Item] = Field(default_factory=list, max_length=6)
    terms: list[Item] = Field(default_factory=list, max_length=4)
    clarifications: list[Item] = Field(default_factory=list, max_length=6)

    @model_validator(mode='after')
    def check(self):
        seen = set()
        for name, items in self.groups():
            texts = set()
            for item in items:
                if (item.id in seen or item.text in texts or not item.text.strip()
                        or item.source_end - item.source_start != len(item.text)
                        or len(item.text) > (512 if name == 'goal' else 256)):
                    raise ValueError('invalid_memory_item')
                seen.add(item.id)
                texts.add(item.text)
        return self

    def groups(self):
        return [('goal', [self.goal] if self.goal else []),
                ('constraints', self.constraints), ('terms', self.terms),
                ('clarifications', self.clarifications)]


class Change(StrictModel):
    field: Literal['goal', 'constraints', 'terms', 'clarifications']
    action: Literal['set', 'remove']
    item_id: str | None
    quote: str


class Patch(StrictModel):
    changes: list[Change] = Field(max_length=17)


class CombinedResponse(StrictModel):
    grounded: GroundedResponse
    memory_update: Patch


class EmptyRequest(StrictModel):
    pass


class MessageRequest(StrictModel):
    message: str = Field(min_length=1, max_length=20000)
    expected_revision: int = Field(ge=0)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.message.strip():
            raise ValueError('blank_message')
        return self


def reduce_memory(previous, patch, current_user, turn):
    """Validate all proposals before returning a private candidate. No writes."""
    previous = TaskMemory.model_validate(previous)
    patch = Patch.model_validate(patch)
    groups = {name: [x.model_dump() for x in items] for name, items in previous.groups()}
    seen = set()
    for index, change in enumerate(patch.changes):
        items = groups[change.field]
        original = dict(previous.groups())[change.field]
        old = next((x for x in original if x.id == change.item_id), None)
        if not change.quote.strip() or change.quote not in current_user:
            raise ValueError('quote_not_in_current_user')
        if len(change.quote) > (512 if change.field == 'goal' else 256):
            raise ValueError('quote_too_long')
        if change.item_id is not None and old is None:
            raise ValueError('unknown_memory_target')
        if change.action == 'remove' and old is None:
            raise ValueError('remove_requires_target')
        if change.field == 'goal' and previous.goal and old is None:
            raise ValueError('goal_requires_target')
        identity = (change.field, change.item_id or ('goal' if change.field == 'goal' else change.quote))
        if identity in seen:
            raise ValueError('duplicate_memory_operation')
        seen.add(identity)
        if change.action == 'remove':
            items[:] = [x for x in items if x['id'] != change.item_id]
            continue
        identical = next((x for x in items if x['text'] == change.quote), None)
        if identical:
            if old is not None and identical['id'] != old.id:
                raise ValueError('duplicate_memory_text')
            continue
        start = current_user.index(change.quote)
        item = dict(id=old.id if old else f'm{turn}_{index + 1}', text=change.quote,
                    source_user_turn=turn, source_start=start, source_end=start + len(change.quote))
        if old:
            items[:] = [item if x['id'] == old.id else x for x in items]
        else:
            items.append(item)
    if len(groups['goal']) > 1:
        raise ValueError('multiple_goals')
    candidate = {**groups, 'goal': groups['goal'][0] if groups['goal'] else None}
    return TaskMemory.model_validate(candidate).model_dump()
