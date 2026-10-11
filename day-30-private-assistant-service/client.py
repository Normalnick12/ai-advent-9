"""Terminal client. History lives only in RAM; HTTPS required off loopback."""
import argparse
import json
import os
import sys
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
import laa_service  # locate existing core, without importing FastAPI
import httpx
from chat_context import history_bytes
from grounded_explain import render


def service_url(value):
    try:
        url = urlsplit(value)
        if (url.scheme not in {"http", "https"} or not url.hostname or url.username is not None
                or url.password is not None or url.path not in {"", "/"} or url.query or url.fragment
                or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value):
            raise ValueError
        if url.scheme == "http" and url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError
        return value.rstrip("/")
    except ValueError:
        raise ValueError("Use HTTPS, or HTTP on loopback only.") from None


class ChatClient:
    def __init__(self, base, token, file_id, *, transport=None):
        self.base, self.file_id = service_url(base), file_id
        self.history = []
        self.http = httpx.Client(timeout=135, trust_env=False, follow_redirects=False,
                                 headers={"Authorization": "Bearer " + token, "Accept-Encoding": "identity"},
                                 transport=transport)

    def reset(self, file_id=None):
        self.history.clear()
        if file_id is not None:
            self.file_id = file_id

    def ask(self, question):
        payload = {"file_id": self.file_id, "question": question, "history": self.history}
        with self.http.stream("POST", self.base + "/v1/chat", json=payload) as response:
            raw = bytearray()
            for part in response.iter_bytes():
                if len(raw) + len(part) > 2 * 1024 * 1024:
                    raise ValueError("Response too large.")
                raw.extend(part)
            if response.status_code != 200:
                # Do not print arbitrary server content or submitted input on errors.
                raise ValueError("HTTP request failed: " + str(response.status_code))
            result = json.loads(raw)
        if result.get("mechanical_validation") != "passed" or result.get("semantic_status") != "not_evaluated":
            raise ValueError("Invalid response contract.")
        text = render(result["result"], result["sources"])
        self.history.append({"user": question, "assistant": text})
        dropped = False
        while len(self.history) > 2 or len(history_bytes(self.history)) > 8192:
            self.history.pop(0)
            dropped = True
        return text, dropped

    def close(self):
        self.reset()
        self.http.close()


def main():
    parser = argparse.ArgumentParser(description="Chat with the optional architecture service")
    parser.add_argument("--url", default="http://127.0.0.1:8030")
    parser.add_argument("--file-id", required=True)
    args = parser.parse_args()
    token = os.getenv("LAA_CLIENT_TOKEN")
    if not token:
        print("Set LAA_CLIENT_TOKEN in this process environment.", file=sys.stderr)
        return 2
    client = None
    try:
        client = ChatClient(args.url, token, args.file_id)
        print("/reset, /file ID, /quit. Answers require semantic review.")
        while True:
            try:
                question = input("> ")
            except EOFError:
                break
            if question == "/quit":
                break
            if question == "/reset" or question.startswith("/file "):
                client.reset(question[6:].strip() if question.startswith("/file ") else None)
                print("History cleared.")
                continue
            try:
                text, dropped = client.ask(question)
                print(text)
                if dropped:
                    print("Old complete history pairs removed to fit the limit.")
            except Exception:
                print("Request failed; history unchanged. Check safe server status.", file=sys.stderr)
    except KeyboardInterrupt:
        return 130
    except Exception:
        print("Client failed. Check URL, token and dependencies.", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
