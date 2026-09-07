from app.agent_sessions import AgentSession
from app.llm_client import AgentConfig, ConversationMessage, LlmClient, LlmResult


class SimpleAgent:
    def __init__(self, client: LlmClient) -> None:
        self._client = client
        self.config = AgentConfig()

    async def run_turn(self, session: AgentSession, message: str) -> LlmResult:
        session.begin_turn()
        try:
            user = ConversationMessage("user", message)
            result = await self._client.complete((*session.history, user), self.config)
            if result.status == "completed":
                if not result.reply or not result.reply.strip() or result.error_code:
                    return LlmResult(
                        "error", error_code="llm_invalid_response",
                        error_message="Модель вернула непригодный ответ. Попробуйте ещё раз.",
                    )
                session.commit(user, ConversationMessage("assistant", result.reply))
            return result
        finally:
            session.end_turn()
