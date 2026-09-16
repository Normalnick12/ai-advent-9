"""Provider-independent task state, definitions and pure event resolution."""
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def canonical_task_id(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("noncanonical task identity")
    return value


TaskId = Annotated[str, AfterValidator(canonical_task_id)]
StateCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]
ActionCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
MachineId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*-v[1-9][0-9]*$")]
TaskStatus = Literal["ACTIVE", "PAUSED"]
Revision = Annotated[int, Field(ge=0)]


class TaskStateError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(code)


class FrozenStateModel(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class TaskState(FrozenStateModel):
    task_id: TaskId
    machine_id: MachineId
    state_id: StateCode
    status: TaskStatus = "ACTIVE"
    revision: Revision = 0


class StateDefinition(FrozenStateModel):
    state_id: StateCode
    phase: ActionCode
    step: ActionCode
    expected_action: ActionCode
    is_terminal: bool = False


class TransitionEvent(FrozenStateModel):
    event: StateCode


class StateTransition(FrozenStateModel):
    source: StateCode
    event: StateCode
    target: StateCode


class TaskStateDefinition(FrozenStateModel):
    machine_id: MachineId
    initial_node: StateCode
    nodes: tuple[StateDefinition, ...]
    transitions: tuple[StateTransition, ...]

    @model_validator(mode="after")
    def valid_definition(self):
        nodes = {n.state_id: n for n in self.nodes}
        if len(nodes) != len(self.nodes) or self.initial_node not in nodes:
            raise ValueError("duplicate nodes or missing initial node")
        edges = set()
        for edge in self.transitions:
            key = (edge.source, edge.event)
            if (edge.source not in nodes or edge.target not in nodes or key in edges
                    or nodes[edge.source].is_terminal or edge.event in {"PAUSE", "RESUME"}):
                raise ValueError("invalid or ambiguous transition")
            edges.add(key)
        return self

    def validate_state(self, state: TaskState) -> StateDefinition:
        if state.machine_id != self.machine_id:
            raise TaskStateError("machine_version_incompatible", 409)
        node = next((n for n in self.nodes if n.state_id == state.state_id), None)
        if node is None or (node.is_terminal and state.status == "PAUSED"):
            raise TaskStateError("task_state_invalid", 500)
        return node

    def initial(self, task_id: str) -> TaskState:
        return TaskState(task_id=task_id, machine_id=self.machine_id, state_id=self.initial_node)

    def allowed_events(self, state: TaskState) -> tuple[str, ...]:
        node = self.validate_state(state)
        if node.is_terminal:
            return ()
        if state.status == "PAUSED":
            return ("RESUME",)
        return (*(e.event for e in self.transitions if e.source == state.state_id), "PAUSE")

    def view(self, state: TaskState) -> dict:
        node = self.validate_state(state)
        return {**state.model_dump(), **node.model_dump(), "allowed_events": self.allowed_events(state)}


def resolve(state: TaskState, event: str, definition: TaskStateDefinition) -> TaskState:
    """No I/O. A successful result advances exactly one revision."""
    if event not in definition.allowed_events(state):
        raise TaskStateError("invalid_task_event")
    values = state.model_dump()
    if event in {"PAUSE", "RESUME"}:
        values["status"] = "PAUSED" if event == "PAUSE" else "ACTIVE"
    else:
        values["state_id"] = next(e.target for e in definition.transitions
                                  if e.source == state.state_id and e.event == event)
    values["revision"] += 1
    result = TaskState.model_validate(values)
    definition.validate_state(result)
    return result
