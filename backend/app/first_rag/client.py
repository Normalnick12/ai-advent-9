from app.openai_responses_llm_client import OpenAIResponsesLlmClient


class ObservedClient(OpenAIResponsesLlmClient):
    """Keep returned output (including incomplete text); reuse existing normalization."""

    def __init__(self):
        super().__init__()
        self.observed_output = None

    async def complete(self, messages, config):
        self.observed_output = None
        return await super().complete(messages, config)

    def _normalize(self, response):
        self.observed_output = {
            "response_id": getattr(response, "id", None),
            "status": getattr(response, "status", None),
            "output": [item.model_dump(mode="json") for item in (getattr(response, "output", None) or [])],
        }
        return super()._normalize(response)
