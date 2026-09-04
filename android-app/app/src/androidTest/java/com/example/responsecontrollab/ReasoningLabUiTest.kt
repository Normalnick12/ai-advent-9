package com.example.responsecontrollab

import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.ErrorInfoDto
import com.example.responsecontrollab.data.OptimizationSolutionDto
import com.example.responsecontrollab.data.ReasoningExperimentConfigDto
import com.example.responsecontrollab.data.ReasoningLabBatchResponseDto
import com.example.responsecontrollab.data.StrategyResultDto
import com.example.responsecontrollab.data.TokenUsageDto
import com.example.responsecontrollab.data.VerificationDetailsDto
import com.example.responsecontrollab.theme.ResponseControlLabTheme
import com.example.responsecontrollab.ui.reasoning.ReasoningLabContent
import com.example.responsecontrollab.ui.reasoning.ReasoningLabUiState
import org.junit.Rule
import org.junit.runner.RunWith
import org.junit.Test

@RunWith(AndroidJUnit4::class)
class MetaPromptExpansionUiTest {
  @get:Rule val composeRule = createComposeRule()

  @Test
  fun generatedPromptExpandsAndCollapses() {
    val generatedPrompt = "Проверяй все допустимые множества полным перебором."
    composeRule.setContent {
      ResponseControlLabTheme {
        ReasoningLabContent(
          state = metaPromptContentState(generatedPrompt),
          onRun = {},
          onBack = {},
        )
      }
    }

    composeRule
      .onNodeWithText("Показать сгенерированный промпт")
      .performScrollTo()
      .performClick()
    composeRule.onNodeWithText(generatedPrompt).performScrollTo().assertIsDisplayed()

    composeRule
      .onNodeWithText("Скрыть сгенерированный промпт")
      .performScrollTo()
      .performClick()
    composeRule.onAllNodesWithText(generatedPrompt).assertCountEquals(0)
  }

  @Test
  fun partialFailureKeepsSuccessfulCardAndReadableMetrics() {
    composeRule.setContent {
      ResponseControlLabTheme {
        ReasoningLabContent(
          state = partialFailureContentState(),
          onRun = {},
          onBack = {},
        )
      }
    }

    composeRule.onNodeWithText("Прямой ответ").performScrollTo().assertIsDisplayed()
    composeRule
      .onAllNodesWithText("Токены: вход 20, выход 16, рассуждение 6, всего 36")[0]
      .performScrollTo()
      .assertIsDisplayed()
    composeRule.onNodeWithText("Пошаговое решение").performScrollTo().assertIsDisplayed()
    composeRule
      .onNodeWithText("Ошибка стратегии: OpenAI временно недоступен.")
      .performScrollTo()
      .assertIsDisplayed()
  }
}

internal fun metaPromptContentState(generatedPrompt: String): ReasoningLabUiState.Content {
  val solution =
    OptimizationSolutionDto(
      selected_features = listOf("A", "C", "F", "G"),
      total_cost = 15,
      total_value = 29,
      explanation = "Проверено.",
    )
  return ReasoningLabUiState.Content(
    ReasoningLabBatchResponseDto(
      request_id = "ui-test",
      config =
        ReasoningExperimentConfigDto(
          model = "gpt-5.6",
          reasoning_effort = "medium",
          reasoning_mode = "standard",
          max_output_tokens = 1200,
          prompt_cache_mode = "explicit",
          story_point_limit = 15,
        ),
      reference_solution = solution,
      results =
        listOf(
          StrategyResultDto(
            strategy = "META_PROMPT",
            display_name = "Мета-промпт",
            correct = true,
            latency_ms = 200,
            usage = TokenUsageDto(20, 16, 6, 36),
            api_call_count = 2,
            solution = solution,
            verification =
              VerificationDetailsDto(
                feasible = true,
                optimal = true,
                totals_match = true,
                calculated_cost = 15,
                calculated_value = 29,
                violations = emptyList(),
              ),
            generated_prompt = generatedPrompt,
          )
        ),
    )
  )
}

private fun partialFailureContentState(): ReasoningLabUiState.Content {
  val content = metaPromptContentState("Сгенерированный промпт.")
  val successful = content.batch.results.single().copy(
    strategy = "DIRECT",
    display_name = "ignored",
    generated_prompt = null,
  )
  val failed =
    successful.copy(
      strategy = "STEP_BY_STEP",
      display_name = "ignored",
      correct = false,
      api_call_count = 1,
      solution = null,
      verification =
        VerificationDetailsDto(
          feasible = false,
          optimal = false,
          totals_match = false,
          calculated_cost = 0,
          calculated_value = 0,
          violations = listOf("Ошибка стратегии."),
        ),
      error = ErrorInfoDto("openai_upstream_error", "OpenAI временно недоступен."),
    )
  return ReasoningLabUiState.Content(content.batch.copy(results = listOf(successful, failed)))
}
