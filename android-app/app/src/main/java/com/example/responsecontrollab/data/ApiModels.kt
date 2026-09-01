package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable

@Serializable
data class GenerationControlsDto(
  val structured_output: Boolean = false,
  val max_output_tokens: Int? = null,
  val finish_instruction: Boolean = false,
)

@Serializable
data class GenerateRequestDto(
  val prompt: String,
  val controls: GenerationControlsDto = GenerationControlsDto(),
)

@Serializable
data class IngredientDto(val name: String, val weight_grams: Int, val order: Int)

@Serializable
data class RecipeStepDto(val order: Int, val description: String)

@Serializable
data class RecipeDto(
  val recipe_name: String,
  val ingredients: List<IngredientDto>,
  val steps: List<RecipeStepDto>,
)

@Serializable data class ErrorInfoDto(val code: String, val message: String)

@Serializable
data class GenerateResponseDto(
  val request_id: String? = null,
  val content: String? = null,
  val recipe: RecipeDto? = null,
  val status: String,
  val output_tokens: Int? = null,
  val controls: GenerationControlsDto,
  val incomplete_reason: String? = null,
  val error: ErrorInfoDto? = null,
)
