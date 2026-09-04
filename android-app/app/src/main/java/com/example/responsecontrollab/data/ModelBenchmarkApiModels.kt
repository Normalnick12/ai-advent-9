package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class ModelBenchmarkConfigDto(
  val benchmark_version: String,
  val prompt: String,
  val instructions: String,
  val fingerprint: String,
  val api: String,
  val reasoning_effort: String,
  val max_output_tokens: Int,
  val temperature: String,
  val top_p: String,
  val strict_output: Boolean,
  val max_retries: Int,
  val store: Boolean,
  val service_tier: String,
  val execution: String,
  val upstream_timeout_seconds: Int,
)

@Serializable
data class BenchmarkModelOptionDto(val id: String, val display_name: String, val tier: String)

@Serializable
data class BenchmarkRoleDto(
  val id: String,
  val display_name: String,
  val default_model_id: String,
  val allowed_model_ids: List<String>,
)

@Serializable
data class ModelBenchmarkCatalogDto(
  val benchmark_version: String,
  val config: ModelBenchmarkConfigDto,
  val models: List<BenchmarkModelOptionDto>,
  val roles: List<BenchmarkRoleDto>,
)

@Serializable
data class ModelBenchmarkRunRequestDto(val models: Map<String, String>)

@Serializable
data class BenchmarkQualityDto(val correct_count: Int, val total_tasks: Int)

@Serializable
data class BenchmarkTaskDto(
  val task_id: String,
  val verdict: String,
  val actual_answer: JsonObject? = null,
  val reference_answer: JsonObject? = null,
)

@Serializable
data class BenchmarkUsageDto(
  val input_tokens: Long? = null,
  val cached_input_tokens: Long? = null,
  val cache_write_tokens: Long? = null,
  val output_tokens: Long? = null,
  val reasoning_tokens: Long? = null,
  val total_tokens: Long? = null,
)

@Serializable
data class BenchmarkRatesDto(
  val input: String, val cached_input: String, val cache_write: String, val output: String,
)

@Serializable
data class BenchmarkCostDto(
  val status: String,
  val amount_usd: String? = null,
  val currency: String,
  val reason: String? = null,
  val pricing_model: String? = null,
  val rates: BenchmarkRatesDto? = null,
  val source_url: String? = null,
  val checked_at: String? = null,
  val service_tier: String? = null,
  val formula: String,
)

@Serializable
data class ModelBenchmarkResultDto(
  val role: String,
  val requested_model: String,
  val display_name: String,
  val resolved_model: String? = null,
  val status: String,
  val response_status: String? = null,
  val reason: String? = null,
  val quality: BenchmarkQualityDto? = null,
  val tasks: List<BenchmarkTaskDto>,
  val raw_output: String? = null,
  val latency_ms: Long,
  val api_call_count: Int,
  val usage: BenchmarkUsageDto,
  val cost: BenchmarkCostDto,
)

@Serializable
data class ModelBenchmarkBatchDto(
  val request_id: String,
  val config: ModelBenchmarkConfigDto,
  val results: List<ModelBenchmarkResultDto>,
  val api_call_count: Int,
)
