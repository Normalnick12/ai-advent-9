"""Fixed three-call MCP control, explicitly not model orchestration."""
import argparse
import asyncio
import json
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
import httpx
from mcp import Client
from composition.server import create_server, Events, NAMES
from collect import collect
from verify import verify


async def control(destination, versions):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    reports = root / "reports"
    reports.mkdir()
    xml = Element("androidx.core")
    SubElement(xml, "core-ktx", versions=",".join(versions))
    requests, events, calls, outputs = [], [], [], []
    def upstream(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=tostring(xml))
    async with Client(create_server(reports, transport=httpx.MockTransport(upstream), events=Events(events.append))) as client:
        schemas = (await client.list_tools()).model_dump(mode="json", by_alias=True)
        assert [tool["name"] for tool in schemas["tools"]] == list(NAMES)
        args = dict(group_id="androidx.core", artifact_id="core-ktx")
        for i, name in enumerate(NAMES):
            result = await client.call_tool(name, args)
            assert not result.is_error, result
            calls.append(dict(type="mcp_call", id=f"offline-{i}", name=name, server_label="dependency_composition",
                arguments=json.dumps(args), output=result.model_dump_json(by_alias=True), status="completed"))
            outputs.append(result.structured_content)
            args = {"lookup" if i == 0 else "report": result.structured_content}
    assert len(requests) == 1 and outputs[0]["versions"] == versions
    receipt = outputs[2]
    operation = dict(operation_id="offline-control", invocation="observed", calls=calls,
        final_text=json.dumps(dict({k: outputs[1][k] for k in ("group_id", "artifact_id", "status", "version_count", "last_three")},
                                  file_id=receipt["file_id"])), request_configuration={"tools":[{"server_url":"offline"}]},
        orchestration="fixed_code_no_model", upstream_requests=requests, final_origin="fixture_not_model")
    disk = collect(receipt["file_id"], root=reports, operation_id=operation["operation_id"], lookup_id=receipt["lookup_id"],
                   revision="offline", endpoint="offline")
    verdict = verify(operation, events, disk)
    for name, data in (("operation", operation), ("events", events), ("file-read", disk), ("schemas", schemas), ("verdict", verdict)):
        (root / (name + ".json")).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert verdict["chain"]["status"] == "PASS", verdict
    print(json.dumps(dict(control="offline", version_count=len(versions), upstream_calls=len(requests),
                         mcp_calls=len(calls), chain=verdict["chain"]["status"], evidence=str(root))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination")
    parser.add_argument("--preflight")
    args = parser.parse_args()
    versions = json.loads(Path(args.preflight).read_text(encoding="utf-8"))["lookup"]["versions"] if args.preflight else ["2", "1", "2", "3-rc01"]
    asyncio.run(control(args.destination, versions))
