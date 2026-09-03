package com.example.responsecontrollab.data

import kotlinx.coroutines.test.runTest
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TemperatureLabRepositoryTest {
  private val json = Json { ignoreUnknownKeys = true }

  @Test
  fun serializationParsesThreeBenchmarkResultsAndNullableFreeFields() {
    val benchmark = json.decodeFromString<TemperatureLabBatchResponseDto>(benchmarkJson())
    val free = json.decodeFromString<TemperatureLabBatchResponseDto>(freeJson())

    assertEquals(listOf(0.0, 0.7, 1.2), benchmark.results.map { it.temperature })
    assertEquals("код старт", benchmark.results.first().variants?.first()?.normalized_name)
    assertEquals(5, benchmark.results.first().validation?.requirements_met)
    assertNull(free.results.first().variants)
    assertNull(free.results.first().validation)
    assertEquals("Свободный ответ", free.results.first().content)
  }

  @Test
  fun repositorySendsPromptExactlyOnceAndUnchanged() = runTest {
    val expected = json.decodeFromString<TemperatureLabBatchResponseDto>(benchmarkJson())
    val api = RecordingTemperatureLabApi(expected)
    val repository = DefaultTemperatureLabRepository(api)
    val prompt = "  Точный prompt\nс пробелами  "

    assertEquals(expected, repository.run(prompt))
    assertEquals(listOf(prompt), api.prompts)
    assertEquals("{\"prompt\":\"  Точный prompt\\nс пробелами  \"}", json.encodeToString(TemperatureLabRunRequestDto(prompt)))
  }

  @Test
  fun temperatureDtosNeverDefineApiKeyFields() {
    val dtoClasses =
      listOf(
        TemperatureLabRunRequestDto::class.java,
        TemperatureExperimentConfigDto::class.java,
        TemperatureVariantDto::class.java,
        RequirementCheckDto::class.java,
        BenchmarkValidationDto::class.java,
        TemperatureResultDto::class.java,
        TemperatureLabBatchResponseDto::class.java,
      )

    assertFalse(
      dtoClasses.flatMap { it.declaredFields.toList() }.any { field ->
        field.name.contains("api", ignoreCase = true) &&
          field.name.contains("key", ignoreCase = true)
      }
    )
  }

  private class RecordingTemperatureLabApi(
    private val response: TemperatureLabBatchResponseDto
  ) : TemperatureLabApi {
    val prompts = mutableListOf<String>()

    override suspend fun run(request: TemperatureLabRunRequestDto): TemperatureLabBatchResponseDto {
      prompts += request.prompt
      return response
    }
  }
}

private fun benchmarkJson(): String =
  """
  {
    "request_id":"benchmark-1",
    "mode":"benchmark",
    "mode_message":"Benchmark-режим",
    "config":{
      "model":"gpt-5.6","temperatures":[0.0,0.7,1.2],"reasoning_effort":"none",
      "reasoning_mode":"standard","max_output_tokens":600,"top_p":"default",
      "prompt_cache_mode":"explicit","output_contract":"strict_variants",
      "temperature_only_variable":true
    },
    "results":[
      {
        "temperature":0.0,"status":"completed","latency_ms":100,
        "usage":{"input_tokens":10,"output_tokens":20,"reasoning_tokens":0,"total_tokens":30},
        "variants":[{"name":"Код Старт","slogan":"Готовься уверенно","normalized_name":"код старт"}],
        "validation":{"requirements_met":5,"total_requirements":5,"checks":[]}
      },
      {
        "temperature":0.7,"status":"error","latency_ms":90,
        "usage":{"input_tokens":0,"output_tokens":0,"reasoning_tokens":0,"total_tokens":0},
        "error":{"code":"openai_upstream_error","message":"OpenAI недоступен."}
      },
      {
        "temperature":1.2,"status":"completed","latency_ms":110,
        "usage":{"input_tokens":10,"output_tokens":20,"reasoning_tokens":0,"total_tokens":30},
        "variants":[{"name":"Dev Рывок","slogan":"Прокачай навыки","normalized_name":"dev рывок"}],
        "validation":{"requirements_met":5,"total_requirements":5,"checks":[]}
      }
    ]
  }
  """.trimIndent()

private fun freeJson(): String =
  """
  {
    "request_id":"free-1",
    "mode":"free",
    "mode_message":"Автопроверка benchmark недоступна для произвольного запроса.",
    "config":{
      "model":"gpt-5.6","temperatures":[0.0,0.7,1.2],"reasoning_effort":"none",
      "reasoning_mode":"standard","max_output_tokens":600,"top_p":"default",
      "prompt_cache_mode":"explicit","output_contract":"text",
      "temperature_only_variable":true
    },
    "results":[
      {
        "temperature":0.0,"status":"completed","latency_ms":100,
        "usage":{"input_tokens":10,"output_tokens":20,"reasoning_tokens":0,"total_tokens":30},
        "content":"Свободный ответ"
      },
      {
        "temperature":0.7,"status":"completed","latency_ms":101,
        "usage":{"input_tokens":10,"output_tokens":20,"reasoning_tokens":0,"total_tokens":30},
        "content":"Второй ответ"
      },
      {
        "temperature":1.2,"status":"completed","latency_ms":102,
        "usage":{"input_tokens":10,"output_tokens":20,"reasoning_tokens":0,"total_tokens":30},
        "content":"Третий ответ"
      }
    ]
  }
  """.trimIndent()
