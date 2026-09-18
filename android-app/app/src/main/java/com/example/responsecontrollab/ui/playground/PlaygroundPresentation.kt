package com.example.responsecontrollab.ui.playground

import com.example.responsecontrollab.data.PlaygroundReceipt

fun evidenceLabel(value: String?): String = when (value) {
  "not_applicable" -> "Not applicable — не применимо"
  "not_attempted" -> "Not attempted — не выполнялось"
  "not_required" -> "Not required — не требовалось"
  "unavailable", null -> "Unavailable — недоступно"
  "not_checked" -> "Not checked — не проверялось"
  "failed", "error" -> "Failed — ошибка"
  "unknown" -> "Unknown — исход неизвестен"
  "passed", "checked" -> "Passed — проверено"
  "committed" -> "Committed — пара сохранена"
  "dispatched" -> "Dispatched — запрос отправлен"
  "not_dispatched" -> "Not dispatched — запрос не отправлен"
  else -> value
}
fun outcomeLabel(value: String): String = when (value) {
  "forward_applied" -> "Forward applied — переход применён"
  "recovery_applied" -> "Recovery applied — возврат применён"
  "rejected" -> "Forbidden transition rejected — переход отклонён"
  "pause_applied" -> "Задача приостановлена"
  "resume_applied" -> "Задача возобновлена"
  "accepted" -> "Ответ принят"
  "candidate_refused", "request_refused" -> "Отказ по ограничениям задачи"
  "technical_error" -> "Техническая ошибка"
  else -> value
}
data class PlaygroundSummary(val outcome: String, val provider: String, val conversation: String, val coverage: String)
fun summary(receipt: PlaygroundReceipt): PlaygroundSummary = PlaygroundSummary(
  outcome=outcomeLabel(receipt.outcome),
  provider="${evidenceLabel(receipt.provider_dispatch)}; вызовов: ${receipt.generation_calls}",
  conversation=if (receipt.operation == "lifecycle") "Без изменений; commit: не применимо"
    else evidenceLabel(receipt.turn?.commit_status),
  coverage=if (receipt.operation == "lifecycle") "Проверки ответа: не применимо"
    else "Проверяются 4 coding decisions и структура ответа. Семантика текста и кода не проверяется.",
)
