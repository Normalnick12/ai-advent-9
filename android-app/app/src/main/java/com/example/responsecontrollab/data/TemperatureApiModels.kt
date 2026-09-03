package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable

const val CANONICAL_TEMPERATURE_PROMPT = """Придумай ровно 5 названий для мобильного приложения, которое помогает разработчикам готовиться к техническим собеседованиям.

Для каждого названия придумай короткий рекламный слоган.

Требования:

1. Название должно состоять из 1–2 слов.
2. Все 5 названий должны различаться.
3. В названиях нельзя использовать отдельные слова «Interview», «AI» и «ИИ».
4. Каждый слоган должен содержать не более 8 слов.
5. Названия и слоганы должны быть уместны для продукта подготовки разработчиков к техническим собеседованиям.

Не добавляй вступление, заключение или дополнительные комментарии."""

@Serializable
data class TemperatureLabRunRequestDto(val prompt: String)

@Serializable
data class TemperatureExperimentConfigDto(
  val model: String,
  val temperatures: List<Double>,
  val reasoning_effort: String,
  val reasoning_mode: String,
  val max_output_tokens: Int,
  val top_p: String,
  val prompt_cache_mode: String,
  val output_contract: String,
  val temperature_only_variable: Boolean,
)

@Serializable
data class TemperatureVariantDto(
  val name: String,
  val slogan: String,
  val normalized_name: String,
)

@Serializable
data class RequirementCheckDto(
  val id: String,
  val label: String,
  val passed: Boolean,
)

@Serializable
data class BenchmarkValidationDto(
  val requirements_met: Int,
  val total_requirements: Int,
  val checks: List<RequirementCheckDto>,
)

@Serializable
data class TemperatureResultDto(
  val temperature: Double,
  val status: String,
  val latency_ms: Long,
  val usage: TokenUsageDto,
  val variants: List<TemperatureVariantDto>? = null,
  val content: String? = null,
  val validation: BenchmarkValidationDto? = null,
  val error: ErrorInfoDto? = null,
)

@Serializable
data class TemperatureLabBatchResponseDto(
  val request_id: String,
  val mode: String,
  val mode_message: String,
  val config: TemperatureExperimentConfigDto,
  val results: List<TemperatureResultDto>,
)
