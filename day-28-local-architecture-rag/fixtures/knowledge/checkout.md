# Checkout team conventions

## CheckoutCoordinator responsibility

CheckoutCoordinator is the application-layer coordinator for the interactive checkout use case. A coordinator sequences collaborators; it does not own payment processing, persistence implementation, or screen rendering. A type name alone does not establish whether a dependency is an interface.

## Checkout success boundary

For interactive checkout, navigation to a receipt and cart clearing are permitted only after an approved payment. An empty cart must return before any charge attempt. A declined payment must not clear the cart or navigate to a receipt.

## Checkout guarantees need evidence

Interactive checkout has no documented atomic transaction across payment, cart storage, and navigation. Calling these collaborators in order does not demonstrate rollback, retry, idempotency, or exception recovery. Those properties require additional implementation evidence.
