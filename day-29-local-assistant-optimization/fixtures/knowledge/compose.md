# Catalog architecture conventions

## Ownership in the catalog screen

Compose renders UI state and forwards user actions. CatalogViewModel owns screen UI state and delegates catalog operations and navigation requests to CatalogCoordinator. The coordinator implementation is outside the selected file; its storage and network behavior need implementation evidence.

## State and effects in the catalog screen

Expose read-only StateFlow for current UI state. Collect UI state with collectAsStateWithLifecycle in the route. Tie item loading to the selected item and ViewModel using LaunchedEffect keys. These conventions do not promise exactly-once execution, persistence, rollback, retries, or cancellation of work launched in a separate scope.
