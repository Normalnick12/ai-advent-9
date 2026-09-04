package com.example.responsecontrollab

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.benchmark.ModelBenchmarkViewModel
import kotlinx.coroutines.CompletableDeferred
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ModelBenchmarkUiTest {
  @get:Rule val composeRule = createAndroidComposeRule<MainActivity>()
  private var calls = 0
  private var catalogCalls = 0
  private var failCatalog = false
  private val pending = CompletableDeferred<ModelBenchmarkBatchDto>()
  private lateinit var vm: ModelBenchmarkViewModel

  @Before fun injectRepository() {
    composeRule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm = ViewModelProvider(activity, ModelBenchmarkViewModel.factory(object : ModelBenchmarkRepository {
        override suspend fun catalog(): ModelBenchmarkCatalogDto {
          catalogCalls++
          if (failCatalog) error("offline")
          return modelBenchmarkCatalogFixture()
        }
        override suspend fun run(models: Map<String, String>): ModelBenchmarkBatchDto {
          calls++
          return pending.await()
        }
      }))[ModelBenchmarkViewModel::class.java]
    }
    composeRule.activityRule.scenario.recreate()
  }

  @Test fun selectorsAndReadOnlySettingsDoNotStartRequests() {
    open()
    composeRule.onNodeWithText("Лаборатория моделей").assertIsDisplayed()
    composeRule.onNodeWithTag("model_select_economical").performClick()
    composeRule.onNodeWithTag("model_option_economical_gpt-5.6-sol").performClick()
    composeRule.onNodeWithText("Одна модель выбрана несколько раз:", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithTag("benchmark_parameters").performScrollTo().performClick()
    composeRule.onNodeWithText("Рассуждение: medium · Лимит выхода: 6000").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("temperature: omitted · top_p: omitted").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Строгий JSON: да · Повторов: 0").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Task 1–5: фиксированный тестовый запрос").performScrollTo().assertIsDisplayed()
    composeRule.onAllNodes(hasSetTextAction()).assertCountEquals(0)
    composeRule.runOnIdle { assertEquals(0, calls); assertEquals(1, catalogCalls) }
  }

  @Test fun catalogFailureHasExplicitRetryAndNoLocalFallback() {
    composeRule.runOnIdle { failCatalog = true }
    open()
    composeRule.onNodeWithText("Повторить загрузку каталога").assertIsDisplayed()
    composeRule.onNodeWithTag("model_select_economical").assertDoesNotExist()
    composeRule.onNodeWithTag("benchmark_run").assertIsNotEnabled()
    back(); open()
    composeRule.runOnIdle { assertEquals(1, catalogCalls); failCatalog = false }
    composeRule.onNodeWithText("Повторить загрузку каталога").performClick()
    composeRule.onNodeWithTag("model_select_economical").assertIsDisplayed()
    composeRule.runOnIdle { assertEquals(2, catalogCalls); assertEquals(0, calls) }
  }

  @Test fun runningSessionResultsScrollAndExpansionSurviveNavigationAndRecreation() {
    open()
    composeRule.onNodeWithTag("benchmark_run").performScrollTo().performClick()
    composeRule.onNodeWithTag("benchmark_run").assertIsNotEnabled()
    composeRule.onNodeWithTag("model_select_economical").performScrollTo().assertIsNotEnabled()
    back()
    composeRule.activityRule.scenario.recreate()
    open()
    composeRule.onNodeWithTag("benchmark_loading").performScrollTo().assertIsDisplayed()
    composeRule.runOnIdle { pending.complete(modelBenchmarkBatchFixture()) }
    composeRule.onNodeWithText("4/5").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("5/5").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Нет проверяемого результата").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithTag("benchmark_details_economical").performScrollTo().performClick()
    composeRule.onNodeWithText("Задача 5 — Неверно").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("\"count\": 21", substring = true).performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("\"count\": 24", substring = true).performScrollTo().assertIsDisplayed()
    val scroll = scrollPosition()
    back(); open()
    assertEquals(scroll, scrollPosition(), 1f)
    composeRule.activityRule.scenario.recreate()
    composeRule.onNodeWithText("\"count\": 24", substring = true).assertIsDisplayed()
    composeRule.onNodeWithText("Рассуждение (часть выхода): 90").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Точная сумма: 0.000769 USD").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithTag("benchmark_details_flagship").performScrollTo().performClick()
    composeRule.onNodeWithText("{незавершённый JSON").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Фактическая модель: Нет данных").performScrollTo().assertIsDisplayed()
    composeRule.runOnIdle { assertEquals(1, calls); assertEquals(1, catalogCalls) }
  }

  @Test fun realZeroQualityIsDistinctFromUnverifiedAndUnknownMetrics() {
    composeRule.runOnIdle {
      val batch = modelBenchmarkBatchFixture()
      pending.complete(batch.copy(results = batch.results.mapIndexed { i, result ->
        if (i == 0) result.copy(quality = BenchmarkQualityDto(0, 5)) else result
      }))
    }
    open()
    composeRule.onNodeWithTag("benchmark_run").performScrollTo().performClick()
    composeRule.onNodeWithText("0/5").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("0,000769 USD").performScrollTo().assertIsDisplayed()
    composeRule.onNodeWithText("Нет проверяемого результата").performScrollTo().assertIsDisplayed()
    composeRule.onAllNodesWithText("Нет данных").onFirst().performScrollTo().assertIsDisplayed()
  }

  private fun open() {
    composeRule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_05"))
    composeRule.onNodeWithTag("day_05").performClick()
  }
  private fun back() { composeRule.onNodeWithContentDescription("Назад к дням").performClick() }
  private fun scrollPosition(): Float = composeRule.onNodeWithTag("lesson_05").fetchSemanticsNode()
    .config[SemanticsProperties.VerticalScrollAxisRange].value()
}

internal fun modelBenchmarkCatalogFixture(): ModelBenchmarkCatalogDto {
  val ids = listOf("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol")
  val roles = listOf("economical", "balanced", "flagship")
  val names = listOf("Экономичная", "Сбалансированная", "Флагманская")
  return ModelBenchmarkCatalogDto("test-v1", ModelBenchmarkConfigDto(
    "test-v1", "Task 1–5: фиксированный тестовый запрос", "Return strict JSON", "test-hash",
    "responses", "medium", 6000, "omitted", "omitted", true, 0, false, "default", "concurrent", 240,
  ), ids.mapIndexed { i, id -> BenchmarkModelOptionDto(id, listOf("Luna", "Terra", "Sol")[i], names[i]) },
    roles.mapIndexed { i, role -> BenchmarkRoleDto(role, names[i], ids[i], ids) })
}

internal fun modelBenchmarkBatchFixture(): ModelBenchmarkBatchDto {
  val catalog = modelBenchmarkCatalogFixture()
  return ModelBenchmarkBatchDto("ui-batch", catalog.config, catalog.roles.mapIndexed { i, role ->
    ModelBenchmarkResultDto(
      role.id, role.default_model_id, catalog.models[i].display_name,
      resolved_model = role.default_model_id.takeIf { i != 2 },
      status = if (i == 2) "incomplete" else "completed",
      response_status = if (i == 2) "incomplete" else "completed",
      reason = "max_output_tokens".takeIf { i == 2 },
      quality = if (i == 2) null else BenchmarkQualityDto(if (i == 0) 4 else 5, 5),
      tasks = (1..5).map { task -> BenchmarkTaskDto("task$task",
        if (i == 2) "unverified" else if (i == 0 && task == 5) "incorrect" else "correct",
        actual_answer = if (i == 2) null else buildJsonObject { put(if (task == 5) "count" else "answer", if (task == 5 && i == 0) 21 else 24) },
        reference_answer = if (i == 0 && task == 5) buildJsonObject { put("count", 24) } else null,
      ) },
      raw_output = "{незавершённый JSON".takeIf { i == 2 }, latency_ms = 1500, api_call_count = 1,
      usage = if (i == 2) BenchmarkUsageDto() else BenchmarkUsageDto(50, 0, 0, 100, 90, 150),
      cost = BenchmarkCostDto(if (i == 2) "unavailable" else "available",
        amount_usd = when (i) { 0 -> "0.000769"; 1 -> "0.002"; else -> null }, currency = "USD",
        formula = "((I-C-W)*Ri+C*Rc+W*Rw+O*Ro)/1000000"),
    )
  }, 3)
}
