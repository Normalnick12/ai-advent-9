from app.llm_client import AgentConfig, ConversationMessage


def context_payload(messages: tuple[ConversationMessage, ...], config: AgentConfig,
                    *, include_instructions: bool = True) -> dict:
    payload = {"model": config.model,
               "input": [{"role": item.role, "content": item.content} for item in messages],
               "text": {"format": config.text_format if config.text_format is not None else {"type": "text"}}}
    if include_instructions:
        payload["instructions"] = config.instructions
    if config.reasoning_effort is not None:
        payload["reasoning"] = {"effort": config.reasoning_effort}
    if config.truncation is not None:
        payload["truncation"] = config.truncation
    return payload


def generation_payload(messages: tuple[ConversationMessage, ...], config: AgentConfig) -> dict:
    payload = context_payload(messages, config)
    payload.update(max_output_tokens=config.max_output_tokens, store=False)
    if config.service_tier is not None:
        payload["service_tier"] = config.service_tier
    return payload
