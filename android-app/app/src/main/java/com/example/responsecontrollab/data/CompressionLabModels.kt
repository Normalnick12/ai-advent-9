package com.example.responsecontrollab.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

const val COMPRESSION_VERSION = "day09-gpt4o-mini-tail4-v1"

@Serializable
data class CompressionSummaryDto(
  @SerialName("session_id") val sessionId: String,
  @SerialName("summary_text") val text: String,
  @SerialName("covered_through_position") val boundary: Int,
  @SerialName("config_version") val configVersion: String,
)
@Serializable
data class CompressionSummaryMetadataDto(
  @SerialName("covered_through_position") val boundary: Int,
  @SerialName("summarized_message_count") val messageCount: Int,
  @SerialName("summary_chars") val chars: Int,
  @SerialName("config_version") val configVersion: String,
)
@Serializable
data class CompressionSessionDto(
  @SerialName("session_id") val sessionId: String,
  @SerialName("history_turn_count") val historyTurnCount: Int,
  @SerialName("config_version") val configVersion: String = COMPRESSION_VERSION,
  @SerialName("summary_metadata") val summaryMetadata: CompressionSummaryMetadataDto? = null,
)
@Serializable
data class CompressionSummaryResponseDto(
  @SerialName("session_id") val sessionId: String,
  val summary: CompressionSummaryDto? = null,
)
@Serializable
data class CompressionPhaseDto(
  val status: String = "not_attempted",
  @SerialName("generation_attempted") val generationAttempted: Boolean = false,
  val usage: TokenLabUsageDto? = null,
  val cost: TokenCostDto = TokenCostDto(),
  @SerialName("latency_ms") val latencyMs: Long? = null,
  @SerialName("error_code") val errorCode: String? = null,
  @SerialName("requested_model") val requestedModel: String? = null,
  @SerialName("resolved_model") val resolvedModel: String? = null,
  @SerialName("actual_service_tier") val actualServiceTier: String? = null,
)
@Serializable
data class CompressionContextDto(
  @SerialName("full_input_tokens") val fullInputTokens: Long? = null,
  @SerialName("compressed_input_tokens") val compressedInputTokens: Long? = null,
  @SerialName("token_delta") val tokenDelta: Long? = null,
  @SerialName("percent_delta") val percentDelta: Double? = null,
  @SerialName("history_message_count_before") val historyMessageCountBefore: Int = 0,
  @SerialName("summarized_message_count") val summarizedMessageCount: Int = 0,
  @SerialName("raw_tail_count") val rawTailCount: Int = 0,
  @SerialName("raw_tail_limit") val rawTailLimit: Int = 4,
  @SerialName("covered_through_position") val boundary: Int? = null,
  @SerialName("summary_chars") val summaryChars: Int = 0,
  @SerialName("summary_standalone_tokens") val summaryStandaloneTokens: Long? = null,
  @SerialName("summary_source") val summarySource: String = "not_measured",
  @SerialName("full_source") val fullSource: String = "not_measured",
  @SerialName("compressed_source") val compressedSource: String = "not_measured",
  @SerialName("full_error") val fullError: String? = null,
  @SerialName("compressed_error") val compressedError: String? = null,
  @SerialName("summary_error") val summaryError: String? = null,
  @SerialName("count_calls") val countCalls: Int = 0,
  @SerialName("context_window") val contextWindow: Long = 128000,
  @SerialName("reserved_output_tokens") val reservedOutputTokens: Long = 1200,
  @SerialName("reserve_warning") val reserveWarning: Boolean = false,
)
@Serializable
data class CompressionBranchDto(
  val status: String = "not_attempted",
  val reply: String? = null,
  @SerialName("error_code") val errorCode: String? = null,
  val phase: CompressionPhaseDto = CompressionPhaseDto(),
  val score: Int? = null,
  val facts: Map<String, Boolean>? = null,
)
@Serializable
data class CompressionOperationDto(
  @SerialName("session_id") val sessionId: String,
  @SerialName("history_turn_count") val historyTurnCount: Int,
  @SerialName("request_id") val requestId: String,
  @SerialName("attempt_id") val attemptId: String,
  val kind: String = "send",
  val status: String,
  @SerialName("error_code") val errorCode: String? = null,
  @SerialName("error_message") val errorMessage: String? = null,
  val committed: Boolean = false,
  val reply: String? = null,
  @SerialName("latency_ms") val latencyMs: Long = 0,
  val context: CompressionContextDto? = null,
  @SerialName("summary_phase") val summaryPhase: CompressionPhaseDto = CompressionPhaseDto(),
  @SerialName("response_phase") val responsePhase: CompressionPhaseDto = CompressionPhaseDto(),
  @SerialName("durable_summary") val durableSummary: CompressionSummaryDto? = null,
  @SerialName("compare_summary") val compareSummary: CompressionSummaryDto? = null,
  @SerialName("summary_source") val summarySource: String = "not_loaded",
  @SerialName("snapshot_id") val snapshotId: String? = null,
  val question: String? = null,
  val full: CompressionBranchDto? = null,
  val compressed: CompressionBranchDto? = null,
  @SerialName("scenario_status") val scenarioStatus: String = "not_requested",
)
@Serializable
data class CompressionCompareRequestDto(val question: String,
  @SerialName("scenario_id") val scenarioId: String? = null)
