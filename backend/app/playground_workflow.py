"""Day 15 definition and presentation metadata; the shared resolver remains authoritative."""
from app.checkout_workflow import CHECKOUT
from app.task_state import StateTransition, TaskStateDefinition

CHECKOUT_V2 = TaskStateDefinition(
    machine_id="checkout-v2", initial_node=CHECKOUT.initial_node, nodes=CHECKOUT.nodes,
    transitions=(*CHECKOUT.transitions,
        StateTransition(source="PLANNING_APPROVAL", event="REQUIREMENTS_REVISION_REQUIRED",
                        target="PLANNING_REQUIREMENTS"),
        StateTransition(source="VALIDATION_CHECK", event="VALIDATION_FAILED",
                        target="EXECUTION_IMPLEMENT")),
)
RECOVERY_EVENTS = frozenset({"REQUIREMENTS_REVISION_REQUIRED", "VALIDATION_FAILED"})
EVENT_LABELS = {
    "REQUIREMENTS_READY": "Требования готовы", "PLAN_APPROVED": "Утвердить план",
    "IMPLEMENTATION_READY": "Реализация готова", "VALIDATION_CONFIRMED": "Подтвердить проверку",
    "REQUIREMENTS_REVISION_REQUIRED": "Уточнить требования",
    "VALIDATION_FAILED": "Проверка не пройдена", "PAUSE": "Приостановить", "RESUME": "Возобновить",
}
NODE_LABELS = {
    "PLANNING_REQUIREMENTS": "Требования", "PLANNING_APPROVAL": "Согласование плана",
    "EXECUTION_IMPLEMENT": "Реализация", "VALIDATION_CHECK": "Проверка", "DONE": "Завершено",
}
NEXT_ACTIONS = {
    "PLANNING_REQUIREMENTS": "Уточните требования и подготовьте план.",
    "PLANNING_APPROVAL": "Обсудите и утвердите план либо уточните требования.",
    "EXECUTION_IMPLEMENT": "Обсудите реализацию и подтвердите её готовность.",
    "VALIDATION_CHECK": "Подтвердите проверку либо верните задачу на исправление.",
    "DONE": "Задача завершена. Можно создать новую задачу.",
}
RECOVERY_EXPLANATIONS = {
    "REQUIREMENTS_REVISION_REQUIRED": "Задача возвращена к требованиям. Следующий шаг: уточнить требования и снова согласовать план.",
    "VALIDATION_FAILED": "Проверка не пройдена. Задача возвращена на этап реализации. Следующий шаг: исправить найденные проблемы.",
}
EDUCATIONAL_EVENTS = {
    "PLANNING_APPROVAL": "IMPLEMENTATION_READY",
    "EXECUTION_IMPLEMENT": "VALIDATION_CONFIRMED",
}


def transition_kind(event: str) -> str:
    if event in RECOVERY_EVENTS:
        return "recovery_applied"
    return {"PAUSE": "pause_applied", "RESUME": "resume_applied"}.get(event, "forward_applied")
