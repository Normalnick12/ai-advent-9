"""Capture actual provider-neutral arguments, without knowing any experiment."""
from copy import deepcopy
from dataclasses import asdict


class CapturingClient:
    def __init__(self, delegate, on_call):
        self.delegate, self.on_call, self.request = delegate, on_call, None

    async def complete(self, messages, config):
        self.request = deepcopy({"messages": [asdict(m) for m in messages], "config": asdict(config)})
        self.on_call()
        return await self.delegate.complete(messages, config)
