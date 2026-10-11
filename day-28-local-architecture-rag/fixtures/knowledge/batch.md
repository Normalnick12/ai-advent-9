# Batch settlement conventions

## BatchSettlementCoordinator transaction

Only the nightly BatchSettlementCoordinator runs a database transaction around its settlement ledger writes and retries transient database failures. This rule is scoped to batch settlement, not interactive checkout or CheckoutCoordinator.
