import asyncio
import json
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
from uuid import uuid4

from app.context_policy import SlidingWindowContextPolicy
from app.conversation_store import ConversationStorageError
from app.document_indexing.embedding import EMBEDDING_CONFIG
from app.first_rag.core import read_index, search
from app.grounded_rag.core import abstention, gate, validate
from app.llm_capture import CapturingClient
from app.llm_client import ConversationMessage
from app.openai_agent_payload import generation_payload
from .context import CONFIG, generation_context, retrieval_query
from .models import ChatError, MessageRequest, reduce_memory, strict_json


class EvidenceError(Exception):
    """Stop the caller; a failed checkpoint never authorizes another dispatch."""


class Day25ChatService:
    def __init__(self, store, client, embedder, index=None):
        self.store, self.client, self.embedder = store, client, embedder
        self.index = index
        self.busy = set()

    @contextmanager
    def claim(self, sid):
        if sid in self.busy:
            raise ChatError('session_busy')
        self.busy.add(sid)
        try:
            yield
        finally:
            self.busy.discard(sid)

    def create(self):
        return self.store.create()

    def read(self, sid):
        with self.claim(sid):
            return self.store.read(sid)

    def delete(self, sid):
        with self.claim(sid):
            self.store.delete(sid)

    async def send(self, sid, message, expected_revision, *, observe=None):
        request = MessageRequest(message=message, expected_revision=expected_revision)
        with self.claim(sid):
            before = self.store.read(sid)
            if before['revision'] != request.expected_revision:
                raise ChatError('stale_revision')
            record = dict(attempt_id=str(uuid4()), session_id=sid, user=message, before=before,
                          retrieval={'attempted': False, 'status': 'not_attempted'},
                          generation={'attempted': False, 'status': 'not_attempted', 'request': None},
                          grounded_validation={'status': 'not_run'}, memory_validation={'status': 'not_run'},
                          memory_update=None, memory_update_status=None, grounded=None,
                          commit_status='not_attempted', status='pending', after=None)

            def checkpoint():
                if observe:
                    try:
                        observe(deepcopy(record))
                    except Exception:
                        raise EvidenceError('evidence_write_failed') from None

            async def run():
                history = tuple(ConversationMessage(m['role'], m['content']) for m in before['history'])
                selected = await SlidingWindowContextPolicy().prepare(sid, history)
                start = len(history) - len(selected.messages)
                recent = [dict(position=start+i, role=m.role, content=m.content)
                          for i, m in enumerate(selected.messages)]
                parts, query = retrieval_query(message, before['memory'], recent)
                record.update(recent_history=recent, excluded_positions=list(range(start)), query_parts=parts)
                if self.index is None:
                    self.index = read_index(baseline=True)
                record['index'] = deepcopy(self.index.provenance)
                record['retrieval'].update(attempted=True, status='unknown',
                    input={'texts': [query], **EMBEDDING_CONFIG})
                checkpoint()
                embeddings = await asyncio.to_thread(self.embedder.embed, [query])
                if len(embeddings.vectors) != 1:
                    raise ValueError('invalid_embedding_count')
                hits = search(self.index, embeddings.vectors[0])
                record['retrieval'].update(status='completed', query_vector=embeddings.vectors[0],
                                           hits=hits, usage=embeddings.usage)
                record['gate'] = gate(hits)
                candidate_memory = before['memory']
                if record['gate']['decision'] == 'fail':
                    record.update(grounded=abstention(), memory_update_status='skipped_runtime_gate',
                                  abstention_origin='runtime_gate')
                    record['grounded_validation'] = {'status': 'runtime_gate'}
                    record['memory_validation'] = {'status': 'not_proposed'}
                else:
                    inputs, _ = generation_context(message, before['memory'], recent, hits)
                    record['actual_model_context'] = None

                    def dispatched():
                        actual = tuple(ConversationMessage(**m) for m in capture.request['messages'])
                        sent = generation_payload(actual, CONFIG)
                        if sent != generation_payload(inputs, CONFIG):
                            raise ValueError('context_snapshot_mismatch')
                        record['actual_model_context'] = json.loads(sent['input'][0]['content'])
                        record['generation'].update(attempted=True, status='unknown', request=sent)
                        checkpoint()

                    capture = CapturingClient(self.client, dispatched)
                    outcome = await capture.complete(inputs, CONFIG)
                    record['generation'].update(status='unknown' if outcome.error_code == 'llm_timeout' else outcome.status,
                        outcome=asdict(outcome),
                        observed_output=deepcopy(getattr(self.client, 'observed_output', None)))
                    checkpoint()  # Raw output always precedes validation.
                    if outcome.status != 'completed' or outcome.error_code:
                        record.update(status=outcome.status if outcome.status != 'completed' else 'error',
                                      error_code=outcome.error_code or 'provider_error')
                        return
                    try:
                        raw = strict_json(outcome.reply)
                        if not isinstance(raw, dict) or set(raw) != {'grounded', 'memory_update'}:
                            raise ValueError('invalid_combined_schema')
                    except (ValueError, TypeError):
                        record['grounded_validation'] = {'status': 'validation_failed', 'errors': ['invalid_combined_schema']}
                        record['memory_validation'] = {'status': 'validation_failed', 'errors': ['invalid_combined_schema']}
                        record.update(status='validation_failed', error_code='invalid_combined_schema')
                        return
                    record['grounded_validation'], grounded = validate(
                        json.dumps(raw['grounded'], ensure_ascii=False), record['actual_model_context']['rag_context'])
                    record['memory_update'] = raw['memory_update']
                    try:
                        proposed = reduce_memory(before['memory'], raw['memory_update'], message, before['revision'] + 1)
                        record['memory_validation'] = {'status': 'passed', 'errors': []}
                    except (ValueError, TypeError):
                        proposed = None
                        record['memory_validation'] = {'status': 'validation_failed', 'errors': ['invalid_memory_patch']}
                    if grounded is None or proposed is None:
                        record.update(status='validation_failed', error_code='invalid_combined_payload')
                        return
                    record['grounded'] = grounded
                    if grounded['status'] == 'insufficient_context':
                        record.update(memory_update_status='skipped_model_abstention', abstention_origin='model_semantic')
                    else:
                        candidate_memory = proposed
                        record['memory_update_status'] = 'applied' if proposed != before['memory'] else 'unchanged'
                record['commit_status'] = 'unknown'
                checkpoint()
                after = self.store.commit_turn(sid, expected_revision, message, record['grounded'],
                    candidate_memory, record['memory_update_status'], record['attempt_id'])
                record.update(status='accepted', commit_status='committed', after=after)

            try:
                await run()
            except asyncio.CancelledError:
                record.update(status='cancelled', error_code='cancelled')
                checkpoint()
                raise
            except ConversationStorageError:
                record.update(status='error', error_code='storage_unknown')
            except ChatError:
                raise
            except EvidenceError:
                raise
            except Exception:
                record.update(status='error', error_code='turn_processing_error')
            checkpoint()
            committed = record['commit_status'] == 'committed'
            response = dict(session_id=sid, request_id=record['attempt_id'], status=record['status'],
                committed=committed, grounded=record['grounded'] if committed else None,
                memory_update_status=record['memory_update_status'] if committed else None,
                state=record['after'] if committed else None,
                error=None if committed else dict(code=record.get('error_code', 'turn_failed'),
                                                  message='Ход не подтверждён. История и память доступны через чтение состояния.'))
            return dict(response=response, observation=record)
