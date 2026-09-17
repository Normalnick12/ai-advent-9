"""Provider- and domain-independent evidence for mandatory checks (not a rule DSL)."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RuleSource:
    scope: str
    identity: str
    version: str


@dataclass(frozen=True)
class RuleRef:
    rule_id: str
    source: RuleSource
    description: str


@dataclass(frozen=True)
class InvariantViolation:
    rule: RuleRef
    stage: Literal["request", "candidate"]
    reason: str
    attempted: str | bool
    required: str | bool


class EnforcementUnavailable(Exception):
    """A missing/broken check is a technical error, never a semantic violation."""


@dataclass(frozen=True)
class ValidationResult:
    status: Literal["passed", "violated", "unavailable"]
    checked_rules: tuple[RuleRef, ...] = ()
    violations: tuple[InvariantViolation, ...] = ()

    def require_complete(self, required: tuple[RuleRef, ...]) -> None:
        if (self.status not in ("passed", "violated") or not required
                or len(set(required)) != len(required)
                or len(set(self.checked_rules)) != len(self.checked_rules)
                or set(self.checked_rules) != set(required)
                or any(v.rule not in required for v in self.violations)
                or (self.status == "passed") != (not self.violations)):
            raise EnforcementUnavailable


def assessment(rules: tuple[RuleRef, ...], violations: tuple[InvariantViolation, ...]) -> ValidationResult:
    return ValidationResult("violated" if violations else "passed", rules, violations)
