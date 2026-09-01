from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app, get_openai_service
from app.models import AppliedControls, GenerateResponse


@pytest.mark.asyncio
async def test_generate_endpoint_contract() -> None:
    service = AsyncMock()
    service.generate.return_value = GenerateResponse(
        content="Обычный текст",
        status="completed",
        output_tokens=15,
        controls=AppliedControls(
            structured_output=False,
            max_output_tokens=None,
            finish_instruction=False,
        ),
    )
    app.dependency_overrides[get_openai_service] = lambda: service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/generate",
                json={"prompt": "Один prompt", "controls": {}},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["content"] == "Обычный текст"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    service.generate.assert_awaited_once()
