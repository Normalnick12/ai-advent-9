from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.conversation_store import ConversationStorageError
from .models import ChatError, EmptyRequest, MessageRequest


class ChatRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            try:
                return await handler(request)
            except ChatError as exc:
                code, status = exc.code, exc.status
            except RequestValidationError:
                code, status = 'validation_error', 422
            except ConversationStorageError:
                code, status = 'storage_unknown', 503
            except Exception:
                code, status = 'internal_error', 500
            return JSONResponse(status_code=status, content={'error': {'code': code, 'message': code}})
        return safe


router = APIRouter(prefix='/api/v1/day25/sessions', route_class=ChatRoute)


def get_service(request: Request):
    return request.app.state.day25_chat


@router.post('', status_code=201)
async def create(body: EmptyRequest, service=Depends(get_service)):
    return service.create()


@router.get('/{session_id}')
async def read(session_id: UUID, service=Depends(get_service)):
    return service.read(str(session_id))


@router.post('/{session_id}/messages')
async def send(session_id: UUID, body: MessageRequest, service=Depends(get_service)):
    result = await service.send(str(session_id), body.message, body.expected_revision)
    return result['response']


@router.delete('/{session_id}', status_code=204)
async def delete(session_id: UUID, service=Depends(get_service)):
    service.delete(str(session_id))
    return Response(status_code=204)
