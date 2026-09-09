package com.example.responsecontrollab.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class TokenDiagnosticsDto(
  @SerialName("current_message_tokens") val currentMessageTokens: Long? = null,
  @SerialName("saved_history_tokens") val savedHistoryTokens: Long? = null,
  @SerialName("preflight_input_tokens") val preflightInputTokens: Long? = null,
  @SerialName("current_source") val currentSource: String = "not_measured",
  @SerialName("history_source") val historySource: String = "not_measured",
  @SerialName("full_source") val fullSource: String = "not_measured",
  @SerialName("history_turn_count_before") val historyTurnCountBefore: Int = 0,
  @SerialName("context_window") val contextWindow: Long,
  @SerialName("reserved_output_tokens") val reservedOutputTokens: Long,
  @SerialName("count_calls") val countCalls: Int,
  @SerialName("count_error") val countError: String? = null,
  @SerialName("reserve_warning") val reserveWarning: Boolean = false,
)
@Serializable
data class TokenLabUsageDto(
  @SerialName("input_tokens") val inputTokens: Long? = null,
  @SerialName("cached_input_tokens") val cachedInputTokens: Long? = null,
  @SerialName("cache_write_tokens") val cacheWriteTokens: Long? = null,
  @SerialName("output_tokens") val outputTokens: Long? = null,
  @SerialName("reasoning_tokens") val reasoningTokens: Long? = null,
  @SerialName("total_tokens") val totalTokens: Long? = null,
)
@Serializable
data class TokenCostDto(
  val status: String = "unavailable",
  @SerialName("amount_usd") val amountUsd: String? = null,
  val reason: String? = null,
  @SerialName("pricing_date") val pricingDate: String = "",
  val source: String = "",
  @SerialName("input_rate") val inputRate: String = "",
  @SerialName("cached_input_rate") val cachedInputRate: String = "",
  @SerialName("output_rate") val outputRate: String = "",
)
@Serializable
data class OverflowPreparationDto(
  @SerialName("preparation_id") val preparationId: String,
  val model: String,
  @SerialName("config_version") val configVersion: String,
  val repeats: Int,
  val unit: String,
  val header: String,
  val ending: String,
  @SerialName("message_chars") val messageChars: Int,
  @SerialName("message_utf8_bytes") val messageUtf8Bytes: Int,
  @SerialName("full_payload_bytes") val fullPayloadBytes: Int,
  @SerialName("payload_sha256") val payloadSha256: String,
  @SerialName("sample_start") val sampleStart: String,
  @SerialName("sample_end") val sampleEnd: String,
  @SerialName("created_at") val createdAt: Double,
  @SerialName("expires_at") val expiresAt: Double,
)
@Serializable
data class TokenTurnDto(
  @SerialName("session_id") val sessionId: String,
  @SerialName("history_turn_count") val historyTurnCount: Int,
  @SerialName("request_id") val requestId: String,
  @SerialName("attempt_id") val attemptId: String,
  val status: String,
  val reply: String? = null,
  val error: ChatErrorDto? = null,
  @SerialName("error_origin") val errorOrigin: String? = null,
  @SerialName("generation_attempted") val generationAttempted: Boolean,
  val committed: Boolean,
  val diagnostics: TokenDiagnosticsDto? = null,
  val usage: TokenLabUsageDto? = null,
  val cost: TokenCostDto = TokenCostDto(),
  @SerialName("requested_model") val requestedModel: String? = null,
  @SerialName("resolved_model") val resolvedModel: String? = null,
  @SerialName("requested_service_tier") val requestedServiceTier: String? = null,
  @SerialName("actual_service_tier") val actualServiceTier: String? = null,
  @SerialName("provider_status") val providerStatus: String? = null,
  val preparation: OverflowPreparationDto? = null,
)
@Serializable
data class OverflowExecuteDto(@SerialName("preparation_id") val preparationId: String, val confirm: Boolean)
