package example.checkout

class CheckoutCoordinator(
    private val cart: CartRepository,
    private val payments: PaymentGateway,
    private val navigator: CheckoutNavigator,
) {
    suspend fun checkout(): CheckoutResult {
        val items = cart.items()
        if (items.isEmpty()) return CheckoutResult.EmptyCart

        val amount = items.sumOf { it.priceCents * it.quantity }
        val payment = payments.charge(amount)
        if (!payment.approved) return CheckoutResult.PaymentDeclined

        cart.clear()
        navigator.openReceipt(payment.receiptId)
        return CheckoutResult.Success(payment.receiptId)
    }
}

sealed interface CheckoutResult {
    data object EmptyCart : CheckoutResult
    data object PaymentDeclined : CheckoutResult
    data class Success(val receiptId: String) : CheckoutResult
}
