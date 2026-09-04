package com.example.responsecontrollab.ui.benchmark

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ModelBenchmarkTest {
  @get:Rule val dispatcher = MainDispatcherRule()

  @Test fun catalogIsLazyAndFailureNeedsExplicitRetry() = runTest {
    val repo = FakeBenchmarkRepository()
    val vm = ModelBenchmarkViewModel(repo)
    assertEquals(0, repo.catalogCalls)
    assertTrue(vm.uiState.value.selections.isEmpty())
    repo.failCatalog = true
    vm.onOpen(); advanceUntilIdle()
    vm.onOpen(); advanceUntilIdle()
    assertEquals(1, repo.catalogCalls)
    assertNull(vm.uiState.value.catalog)
    assertTrue(vm.uiState.value.selections.isEmpty())
    repo.failCatalog = false
    vm.loadCatalog(); advanceUntilIdle()
    assertEquals(2, repo.catalogCalls)
    assertEquals(listOf("luna", "terra", "sol"), vm.uiState.value.selections.values.toList())
    assertTrue(repo.runs.isEmpty())
  }

  @Test fun snapshotLocksControlsAndBlocksDuplicateTapsAndVisits() = runTest {
    val repo = FakeBenchmarkRepository()
    val vm = ModelBenchmarkViewModel(repo)
    vm.runComparison()
    assertTrue(repo.runs.isEmpty())
    vm.onOpen(); advanceUntilIdle()
    vm.selectModel("economical", "unknown")
    assertEquals("luna", vm.uiState.value.selections["economical"])
    vm.selectModel("economical", "sol")
    repo.gate = CompletableDeferred()
    vm.runComparison(); vm.runComparison(); vm.onOpen(); runCurrent()
    vm.selectModel("economical", "terra")
    assertEquals("sol", vm.uiState.value.selections["economical"])
    assertEquals(1, repo.runs.size)
    assertEquals("sol", repo.runs.single()["economical"])
    repo.gate!!.complete(Unit); advanceUntilIdle()
    assertFalse(vm.uiState.value.isLoading)
    assertEquals(1, repo.catalogCalls)
    val batch = vm.uiState.value.latestBatch
    vm.selectModel("economical", "terra")
    assertSame(batch, vm.uiState.value.latestBatch)
  }

  @Test fun transportFailureKeepsPreviousBatchWithoutRetry() = runTest {
    val repo = FakeBenchmarkRepository()
    val vm = ModelBenchmarkViewModel(repo)
    vm.onOpen(); advanceUntilIdle()
    vm.runComparison(); advanceUntilIdle()
    val previous = vm.uiState.value.latestBatch
    repo.failRun = true
    vm.runComparison(); advanceUntilIdle()
    vm.onOpen(); advanceUntilIdle()
    assertSame(previous, vm.uiState.value.latestBatch)
    assertEquals(2, repo.runs.size)
    assertNotNull(vm.uiState.value.runError)
    assertFalse(vm.uiState.value.isLoading)
  }

  @Test fun repositorySendsOnlySelectionsAndPreservesResponse() = runTest {
    var captured: ModelBenchmarkRunRequestDto? = null
    val result = benchmarkBatch()
    val repo = DefaultModelBenchmarkRepository(object : ModelBenchmarkApi {
      override suspend fun catalog() = benchmarkCatalog()
      override suspend fun run(request: ModelBenchmarkRunRequestDto): ModelBenchmarkBatchDto {
        captured = request
        return result
      }
    })
    val selections = linkedMapOf("economical" to "luna", "balanced" to "terra", "flagship" to "sol")
    assertSame(result, repo.run(selections))
    assertEquals("{\"models\":{\"economical\":\"luna\",\"balanced\":\"terra\",\"flagship\":\"sol\"}}", Json.encodeToString(captured!!))
    assertEquals(benchmarkCatalog(), repo.catalog())
  }

  @Test fun nullableUsageAndDecimalCostSurviveSerialization() {
    val result = benchmarkBatch().results.single().copy(
      status = "incomplete", response_status = "incomplete", quality = null,
      raw_output = "{\"task1\":", resolved_model = "resolved-id",
      usage = BenchmarkUsageDto(input_tokens = 953, output_tokens = 6000, reasoning_tokens = 6000, total_tokens = 6953),
    )
    val decoded = Json.decodeFromString<ModelBenchmarkResultDto>(Json.encodeToString(result))
    assertEquals(result, decoded)
    assertNull(decoded.quality)
    assertNull(decoded.usage.cached_input_tokens)
    assertNull(decoded.usage.cache_write_tokens)
    assertEquals("0.000769", decoded.cost.amount_usd)
    assertEquals("resolved-id", decoded.resolved_model)
    assertEquals("{\"task1\":", decoded.raw_output)
  }

  @Test fun dedicatedClientDoesNotChangePreviousDaysBudget() {
    val client = createModelBenchmarkHttpClient()
    assertEquals(10000, client.connectTimeoutMillis)
    assertEquals(30000, client.writeTimeoutMillis)
    assertEquals(260000, client.readTimeoutMillis)
    assertEquals(300000, client.callTimeoutMillis)
    assertFalse(client.retryOnConnectionFailure)
    assertEquals(180000, createBackendHttpClient().readTimeoutMillis)
    assertEquals(190000, createBackendHttpClient().callTimeoutMillis)
  }

  @Test fun smallKnownCostNeverLooksLikeZeroOrUnknown() {
    assertEquals("0,000769 USD", formatBenchmarkCost("0.000769"))
    assertEquals("<0,00000001 USD", formatBenchmarkCost("0.0000000001"))
    assertEquals("0 USD", formatBenchmarkCost("0"))
    assertEquals("Нет данных", formatBenchmarkCost(null))
  }
}

private class FakeBenchmarkRepository : ModelBenchmarkRepository {
  var catalogCalls = 0
  var failCatalog = false
  var failRun = false
  var gate: CompletableDeferred<Unit>? = null
  val runs = mutableListOf<Map<String, String>>()
  override suspend fun catalog(): ModelBenchmarkCatalogDto {
    catalogCalls++
    if (failCatalog) error("offline")
    return benchmarkCatalog()
  }
  override suspend fun run(models: Map<String, String>): ModelBenchmarkBatchDto {
    runs += models
    gate?.await()
    if (failRun) error("offline")
    return benchmarkBatch()
  }
}

private fun benchmarkConfig() = ModelBenchmarkConfigDto(
  "test-v1", "Task 1–5", "Return strict JSON", "fingerprint", "responses", "medium", 6000,
  "omitted", "omitted", true, 0, false, "default", "concurrent", 240,
)

private fun benchmarkCatalog(): ModelBenchmarkCatalogDto {
  val ids = listOf("luna", "terra", "sol")
  return ModelBenchmarkCatalogDto("test-v1", benchmarkConfig(),
    ids.map { BenchmarkModelOptionDto(it, it, "tier") },
    listOf("economical", "balanced", "flagship").mapIndexed { i, role -> BenchmarkRoleDto(role, role, ids[i], ids) },
  )
}

private fun benchmarkBatch() = ModelBenchmarkBatchDto(
  "batch", benchmarkConfig(), listOf(ModelBenchmarkResultDto(
    role = "economical", requested_model = "luna", display_name = "Luna", status = "completed",
    quality = BenchmarkQualityDto(4, 5), tasks = listOf(BenchmarkTaskDto("task5", "incorrect",
      buildJsonObject { put("count", 21) }, buildJsonObject { put("count", 24) })),
    latency_ms = 100, api_call_count = 1, usage = BenchmarkUsageDto(),
    cost = BenchmarkCostDto("available", "0.000769", "USD", formula = "actual usage"),
  )), 3,
)
