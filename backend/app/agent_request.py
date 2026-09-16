"""Small pure preparation of the three existing request sources."""
from copy import deepcopy
from dataclasses import dataclass, replace

from app.llm_client import AgentConfig, ConversationMessage
from app.memory_selection import MemoryContextPolicy, build_context
from app.profile_instructions import render_profile
from app.profiles import AgentProfile
from app.task_state import TaskState, TaskStateDefinition, TaskStateError
from app.task_state_renderer import render_task_state


@dataclass(frozen=True)
class PreparedAgentRequest:
    config: AgentConfig
    policy: MemoryContextPolicy
    query: str
    profile_section: str
    state_section: str

    @property
    def messages(self):
        return (*self.policy.messages, ConversationMessage("user", self.query))


def prepare_agent_request(base_config: AgentConfig, memory: dict, profile: AgentProfile,
                          state: TaskState, definition: TaskStateDefinition, query: str):
    if state.task_id != memory["task_id"] or profile.owner_id != memory["memory_owner_id"]:
        raise TaskStateError("request_source_mismatch")
    policy, _ = build_context(deepcopy(memory))
    profile_text = render_profile(profile)
    state_text = render_task_state(state, definition)
    config = replace(deepcopy(base_config), instructions=(base_config.instructions +
        "\n\nPROFILE\n" + profile_text + "\n\n" + state_text))
    return PreparedAgentRequest(config, policy, query, profile_text, state_text)
