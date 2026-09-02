package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable

@Serializable class ReasoningLabRunRequestDto

@Serializable
data class ReasoningExperimentConfigDto(
  val model: String,
  val reasoning_effort: String,
  val reasoning_mode: String,
  val max_output_tokens: Int,
  val prompt_cache_mode: String,
  val story_point_limit: Int,
)

@Serializable
data class OptimizationSolutionDto(
  val selected_features: List<String>,
  val total_cost: Int,
  val total_value: Int,
  val explanation: String,
)

@Serializable
data class VerificationDetailsDto(
  val feasible: Boolean,
  val optimal: Boolean,
  val totals_match: Boolean,
  val calculated_cost: Int,
  val calculated_value: Int,
  val violations: List<String>,
)

@Serializable
data class TokenUsageDto(
  val input_tokens: Int,
  val output_tokens: Int,
  val reasoning_tokens: Int,
  val total_tokens: Int,
)

@Serializable
data class StrategyResultDto(
  val strategy: String,
  val display_name: String,
  val correct: Boolean,
  val latency_ms: Int,
  val usage: TokenUsageDto,
  val api_call_count: Int,
  val solution: OptimizationSolutionDto? = null,
  val verification: VerificationDetailsDto,
  val error: ErrorInfoDto? = null,
  val generated_prompt: String? = null,
)

@Serializable
data class ReasoningLabBatchResponseDto(
  val request_id: String,
  val config: ReasoningExperimentConfigDto,
  val reference_solution: OptimizationSolutionDto,
  val results: List<StrategyResultDto>,
)
