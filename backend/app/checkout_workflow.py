"""Day 13 workflow fixture; the reusable FSM has no dependency on this module."""
from app.task_state import StateDefinition, StateTransition, TaskStateDefinition

CHECKOUT = TaskStateDefinition(
    machine_id="checkout-v1", initial_node="PLANNING_REQUIREMENTS",
    nodes=(
        StateDefinition(state_id="PLANNING_REQUIREMENTS", phase="planning", step="collect_requirements", expected_action="provide_requirements"),
        StateDefinition(state_id="PLANNING_APPROVAL", phase="planning", step="approve_plan", expected_action="approve_plan"),
        StateDefinition(state_id="EXECUTION_IMPLEMENT", phase="execution", step="implement", expected_action="continue_implementation"),
        StateDefinition(state_id="VALIDATION_CHECK", phase="validation", step="validate", expected_action="provide_validation_result"),
        StateDefinition(state_id="DONE", phase="done", step="complete", expected_action="none", is_terminal=True),
    ),
    transitions=(
        StateTransition(source="PLANNING_REQUIREMENTS", event="REQUIREMENTS_READY", target="PLANNING_APPROVAL"),
        StateTransition(source="PLANNING_APPROVAL", event="PLAN_APPROVED", target="EXECUTION_IMPLEMENT"),
        StateTransition(source="EXECUTION_IMPLEMENT", event="IMPLEMENTATION_READY", target="VALIDATION_CHECK"),
        StateTransition(source="VALIDATION_CHECK", event="VALIDATION_CONFIRMED", target="DONE"),
    ),
)
