package com.example.responsecontrollab.data

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReasoningLabRepositoryTest {
  private val json = Json { ignoreUnknownKeys = true }

  @Test
  fun serializationParsesAllFourStrategyResults() {
    val response = json.decodeFromString<ReasoningLabBatchResponseDto>(batchJson())

    assertEquals(
      listOf("DIRECT", "STEP_BY_STEP", "META_PROMPT", "EXPERT_PANEL"),
      response.results.map(StrategyResultDto::strategy),
    )
    assertEquals("Мета-промпт", response.results[2].display_name)
    assertEquals(2, response.results[2].api_call_count)
    assertEquals("Проверь полный перебор.", response.results[2].generated_prompt)
    assertTrue(response.results[0].correct)
  }

  @Test
  fun repositorySendsOneEmptyRunRequest() = runTest {
    val expected = json.decodeFromString<ReasoningLabBatchResponseDto>(batchJson())
    val api = RecordingReasoningLabApi(expected)
    val repository = DefaultReasoningLabRepository(api)

    val actual = repository.run()

    assertEquals(expected, actual)
    assertEquals(1, api.callCount)
  }

  @Test
  fun reasoningDtosNeverDefineApiKeyFields() {
    val dtoClasses =
      listOf(
        ReasoningLabRunRequestDto::class.java,
        ReasoningExperimentConfigDto::class.java,
        OptimizationSolutionDto::class.java,
        VerificationDetailsDto::class.java,
        TokenUsageDto::class.java,
        StrategyResultDto::class.java,
        ReasoningLabBatchResponseDto::class.java,
      )

    assertFalse(
      dtoClasses
        .flatMap { it.declaredFields.toList() }
        .any { field -> field.name.contains("api", ignoreCase = true) &&
          field.name.contains("key", ignoreCase = true) }
    )
  }

  private class RecordingReasoningLabApi(
    private val response: ReasoningLabBatchResponseDto
  ) : ReasoningLabApi {
    var callCount = 0

    override suspend fun run(request: ReasoningLabRunRequestDto): ReasoningLabBatchResponseDto {
      callCount += 1
      return response
    }
  }
}

private fun batchJson(): String =
  """
  {
    "request_id": "request-1",
    "config": {
      "model": "gpt-5.6",
      "reasoning_effort": "medium",
      "reasoning_mode": "standard",
      "max_output_tokens": 1200,
      "prompt_cache_mode": "explicit",
      "story_point_limit": 15
    },
    "reference_solution": {
      "selected_features": ["A", "C", "F", "G"],
      "total_cost": 15,
      "total_value": 29,
      "explanation": "Полный перебор."
    },
    "results": [
      {
        "strategy": "DIRECT",
        "display_name": "Прямой ответ",
        "correct": true,
        "latency_ms": 100,
        "usage": {"input_tokens": 10, "output_tokens": 8, "reasoning_tokens": 3, "total_tokens": 18},
        "api_call_count": 1,
        "solution": {
          "selected_features": ["A", "C", "F", "G"],
          "total_cost": 15,
          "total_value": 29,
          "explanation": "Проверено."
        },
        "verification": {
          "feasible": true,
          "optimal": true,
          "totals_match": true,
          "calculated_cost": 15,
          "calculated_value": 29,
          "violations": []
        }
      },
      {
        "strategy": "STEP_BY_STEP",
        "display_name": "Пошаговое решение",
        "correct": false,
        "latency_ms": 110,
        "usage": {"input_tokens": 10, "output_tokens": 8, "reasoning_tokens": 3, "total_tokens": 18},
        "api_call_count": 1,
        "verification": {
          "feasible": false,
          "optimal": false,
          "totals_match": false,
          "calculated_cost": 0,
          "calculated_value": 0,
          "violations": ["OpenAI временно недоступен."]
        },
        "error": {"code": "openai_upstream_error", "message": "OpenAI временно недоступен."}
      },
      {
        "strategy": "META_PROMPT",
        "display_name": "Мета-промпт",
        "correct": true,
        "latency_ms": 200,
        "usage": {"input_tokens": 20, "output_tokens": 16, "reasoning_tokens": 6, "total_tokens": 36},
        "api_call_count": 2,
        "solution": {
          "selected_features": ["A", "C", "F", "G"],
          "total_cost": 15,
          "total_value": 29,
          "explanation": "Проверено."
        },
        "verification": {
          "feasible": true,
          "optimal": true,
          "totals_match": true,
          "calculated_cost": 15,
          "calculated_value": 29,
          "violations": []
        },
        "generated_prompt": "Проверь полный перебор."
      },
      {
        "strategy": "EXPERT_PANEL",
        "display_name": "Группа экспертов",
        "correct": true,
        "latency_ms": 120,
        "usage": {"input_tokens": 10, "output_tokens": 8, "reasoning_tokens": 3, "total_tokens": 18},
        "api_call_count": 1,
        "solution": {
          "selected_features": ["A", "C", "F", "G"],
          "total_cost": 15,
          "total_value": 29,
          "explanation": "Проверено."
        },
        "verification": {
          "feasible": true,
          "optimal": true,
          "totals_match": true,
          "calculated_cost": 15,
          "calculated_value": 29,
          "violations": []
        }
      }
    ]
  }
  """.trimIndent()
