import httpx
import pytest
from pydantic import ValidationError

from lookup import lookup, LookupFailure, MAX_BODY_BYTES


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body,outcome,versions", [
    (200, b'<androidx.core><core-ktx versions="2-alpha,1,2"/></androidx.core>', "found", ["2-alpha", "1", "2"]),
    (200, b'<androidx.core><core-ktx versions=""/></androidx.core>', "no_versions", []),
    (200, b'<androidx.core/>', "artifact_not_found", []), (404, b'', "group_not_found", [])])
async def test_normal(status, body, outcome, versions):
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://dl.google.com/dl/android/maven2/androidx/core/group-index.xml"
        return httpx.Response(status, content=body)
    result = await lookup("androidx.core", "core-ktx", transport=httpx.MockTransport(handler), clock=lambda: 42)
    assert result.status == outcome and result.versions == versions and result.checked_at == 42
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body,category", [(302, b'', "upstream_http"), (500, b'', "upstream_http"),
    (200, b'<wrong/>', "upstream_xml"), (200, b'<androidx.core><core-ktx/></androidx.core>', "upstream_xml"),
    (200, b'<androidx.core><core-ktx versions="a, b"/></androidx.core>', "upstream_xml"),
    (200, b'<!DOCTYPE x [<!ENTITY y "secret">]><androidx.core/>', "upstream_xml"),
    (200, b'x' * (MAX_BODY_BYTES + 1), "upstream_response")], ids=["redirect", "http", "root", "attribute", "versions", "dtd", "body_limit"])
async def test_errors_never_retry_redirect(status, body, category):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, content=body, headers={"Location": "https://elsewhere.example"})
    with pytest.raises(LookupFailure, match=category):
        await lookup("androidx.core", "core-ktx", transport=httpx.MockTransport(handler))
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error,category", [(httpx.ReadTimeout, "upstream_timeout"), (httpx.ConnectError, "upstream_network")])
async def test_network_errors(error, category):
    def handler(request):
        raise error("sensitive upstream text", request=request)
    with pytest.raises(LookupFailure, match=category) as failure:
        await lookup("androidx.core", "core-ktx", transport=httpx.MockTransport(handler))
    assert "sensitive" not in str(failure.value)


@pytest.mark.asyncio
async def test_invalid_coordinate_before_network():
    with pytest.raises(ValidationError):
        await lookup("../bad", "x")
