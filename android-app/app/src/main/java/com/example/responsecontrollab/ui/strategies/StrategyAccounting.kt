package com.example.responsecontrollab.ui.strategies

import com.example.responsecontrollab.data.*

data class StrategyTotals(val input: Long = 0, val output: Long = 0, val total: Long = 0, val calls: Int = 0, val complete: Boolean = true)

/** Runtime observations only. Cached/reasoning components never add to totals. */
fun totals(receipts: Collection<StrategyReceipt>, maintenance: Boolean): StrategyTotals {
  var result = StrategyTotals()
  receipts.associateBy { it.attempt_id }.values.forEach { receipt ->
    val phase = if (maintenance) receipt.extraction else receipt.response
    if (phase.attempted) {
      val usage = phase.usage
      val input = usage?.input_tokens?.takeIf { it >= 0 }
      val output = usage?.output_tokens?.takeIf { it >= 0 }
      val actualTotal = usage?.total_tokens?.takeIf { it >= 0 && (input == null || output == null || it == input + output) }
      result = StrategyTotals(result.input + (input ?: 0), result.output + (output ?: 0),
        result.total + (actualTotal ?: ((input ?: 0) + (output ?: 0))),result.calls + 1,
        result.complete && input != null && output != null && (usage?.total_tokens == null || actualTotal != null))
    }
  }
  return result
}
