"""Pure workflow-authority projection; no storage or generation dependencies."""
import json
from app.task_state import TaskState, TaskStateDefinition

TEMPLATE_VERSION = "task-state-v1"
RULES = (
    "TASK_STATE is the authoritative current workflow position, even when older conversation "
    "describes another stage. Memory supplies task facts; PROFILE controls presentation. "
    "Only explicit application events change the node or pause status. Your reply never applies an event. "
    "Answer for the current step; do not restart planning when the task is in execution or validation. "
    "When PAUSED, describe the current task/position and answer clarifications only; do not start "
    "implementation, announce progress or resume. Ask for the explicit Resume action to continue. "
    "expected_action while PAUSED describes what to do AFTER Resume. "
    "When ACTIVE, help with the current step using the supplied task facts. "
    "When the node is terminal, report completion without inventing further workflow steps."
)


def render_task_state(state: TaskState, definition: TaskStateDefinition) -> str:
    node = definition.validate_state(state)
    data = {"state_id": state.state_id, "phase": node.phase, "step": node.step,
            "expected_action": node.expected_action, "status": state.status}
    return RULES + "\nTASK_STATE\n" + json.dumps(data, ensure_ascii=False, sort_keys=True)
