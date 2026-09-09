package com.example.responsecontrollab

import com.example.responsecontrollab.ui.chat.ChatViewModel
import com.example.responsecontrollab.ui.token.TokenLabViewModel
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.benchmark.ModelBenchmarkViewModel
import com.example.responsecontrollab.ui.main.ResponseControlViewModel
import com.example.responsecontrollab.ui.reasoning.ReasoningLabViewModel
import com.example.responsecontrollab.ui.temperature.TemperatureLabViewModel
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class RootNavigationUiTest {
  @get:Rule val composeRule = createAndroidComposeRule<MainActivity>()
  private val responseCalls = mutableListOf<Pair<String, GenerationControlsDto>>()
  private var reasoningCalls = 0
  private var temperatureCalls = 0
  private var chatCalls = 0
  private var benchmarkCalls = 0
  private val tokenRepository = TokenUiRepository()
  private val temperatureResult = CompletableDeferred<TemperatureLabBatchResponseDto>()
  private lateinit var response: ResponseControlViewModel
  private lateinit var temperature: TemperatureLabViewModel

  @Before
  fun useFakeRepositoriesInTheRealActivityStore() {
    // The initial composition never starts requests. Replace its idle ViewModels,
    // then recreate the real Activity so production onCreate reuses these instances.
    composeRule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      ViewModelProvider(activity, TokenLabViewModel.factory(tokenRepository, tokenUiStore()))[TokenLabViewModel.KEY, TokenLabViewModel::class.java]
      ViewModelProvider(activity, ChatViewModel.factory(object : ChatRepository {
        override suspend fun getSession(sessionId: String): ChatSessionDto = error("Unexpected GET")
        override suspend fun createSession(): ChatSessionDto { chatCalls++; error("Unexpected create") }
        override suspend fun sendMessage(sessionId: String, message: String): ChatTurnDto { chatCalls++; error("Unexpected send") }
        override suspend fun deleteSession(sessionId: String) { chatCalls++; error("Unexpected delete") }
      }))[ChatViewModel.DAY_06_KEY, ChatViewModel::class.java]
      ViewModelProvider(activity, ChatViewModel.factory(object : ChatRepository {
        override suspend fun getSession(sessionId: String): ChatSessionDto { chatCalls++; error("Unexpected GET") }
        override suspend fun createSession(): ChatSessionDto { chatCalls++; error("Unexpected create") }
        override suspend fun sendMessage(sessionId: String, message: String): ChatTurnDto { chatCalls++; error("Unexpected send") }
        override suspend fun deleteSession(sessionId: String) { chatCalls++; error("Unexpected delete") }
      }, object : CurrentSessionStore {
        override suspend fun read(): String? = null
        override suspend fun save(sessionId: String) = error("Unexpected save")
        override suspend fun clear() = error("Unexpected clear")
      }))[ChatViewModel.DAY_07_KEY, ChatViewModel::class.java]
      response = ViewModelProvider(activity, ResponseControlViewModel.factory(
        object : ResponseRepository {
          override suspend fun generate(prompt: String, controls: GenerationControlsDto): GenerateResponseDto {
            responseCalls += prompt to controls
            return GenerateResponseDto(
              status = "completed", controls = controls, request_id = "response-test",
              content = "Сохранённый ответ", output_tokens = 12,
            )
          }
        }
      ))[ResponseControlViewModel::class.java]
      ViewModelProvider(activity, ReasoningLabViewModel.factory(
        object : ReasoningLabRepository {
          override suspend fun run(): ReasoningLabBatchResponseDto {
            reasoningCalls++
            return metaPromptContentState("Сохранённый мета-промпт").batch
          }
        }
      ))[ReasoningLabViewModel::class.java]
      temperature = ViewModelProvider(activity, TemperatureLabViewModel.factory(
        object : TemperatureLabRepository {
          override suspend fun run(prompt: String): TemperatureLabBatchResponseDto {
            temperatureCalls++
            return temperatureResult.await()
          }
        }
      ))[TemperatureLabViewModel::class.java]
      ViewModelProvider(activity, ModelBenchmarkViewModel.factory(
        object : ModelBenchmarkRepository {
          override suspend fun catalog() = modelBenchmarkCatalogFixture()
          override suspend fun run(models: Map<String, String>): ModelBenchmarkBatchDto {
            benchmarkCalls++
            return modelBenchmarkBatchFixture()
          }
        }
      ))[ModelBenchmarkViewModel::class.java]
    }
    composeRule.activityRule.scenario.recreate()
  }

  @Test
  fun catalogOpensAllDaysAndBothBackActionsReturnWithoutRequests() {
    composeRule.onNodeWithText("AI Advent").assertIsDisplayed()
    composeRule.onNodeWithTag("day_01").assertDoesNotExist()
    for (day in listOf("02", "03", "04", "05", "06", "07", "08")) {
      open(day)
      composeRule.onNodeWithText("День $day").assertIsDisplayed()
      back()
      open(day)
      Espresso.pressBack()
      composeRule.onNodeWithText("AI Advent").assertIsDisplayed()
    }
    composeRule.runOnIdle {
      assertTrue(responseCalls.isEmpty())
      assertEquals(0, reasoningCalls)
      assertEquals(0, temperatureCalls)
      assertEquals(0, benchmarkCalls)
      assertEquals(0, chatCalls)
      assertEquals(0, tokenRepository.creates)
      assertEquals(0, tokenRepository.executes)
    }
  }

  @Test
  fun backOnCatalogFinishesInsteadOfReopeningLesson() {
    open("03")
    back()
    composeRule.runOnUiThread { composeRule.activity.onBackPressedDispatcher.onBackPressed() }
    composeRule.waitUntil { composeRule.activityRule.scenario.state == androidx.lifecycle.Lifecycle.State.DESTROYED }
  }

  @Test
  fun promptModesAndResultsSurviveVisitsAndActivityRecreation() {
    open("02")
    val prompt = "  Сравни ответы без изменения запроса.  "
    composeRule.onNodeWithText("Запрос").performTextReplacement(prompt)
    Espresso.closeSoftKeyboard()
    composeRule.onNodeWithText("Сравнение").assertIsSelected()
    composeRule.onNodeWithText("Сгенерировать").performScrollTo().performClick()
    composeRule.waitUntil { responseCalls.size == 2 && !response.uiState.value.isLoading }
    composeRule.onNodeWithText("Ответ с ограничениями").performScrollTo().assertIsDisplayed()
    val scroll = scrollPosition("lesson_02")
    back()
    open("03")
    back()
    open("02")
    assertEquals(scroll, scrollPosition("lesson_02"), 1f)
    composeRule.onNodeWithText("Ответ с ограничениями").assertIsDisplayed()
    composeRule.activityRule.scenario.recreate()
    composeRule.onNodeWithText("День 02").assertIsDisplayed()
    assertEquals(scroll, scrollPosition("lesson_02"), 1f)
    composeRule.runOnIdle {
      assertEquals(prompt, response.uiState.value.prompt)
      assertEquals(2, responseCalls.size)
      assertTrue(responseCalls.all { it.first == prompt })
      assertTrue(responseCalls.any { it.second.structured_output })
      assertTrue(responseCalls.any { !it.second.structured_output })
    }
    composeRule.onNodeWithText("Сравнение").performScrollTo().assertIsSelected()
    composeRule.onNodeWithText("Запрос").performScrollTo().assertTextContains(prompt)
  }

  @Test
  fun temperatureRequestSurvivesLeavingAndRecreationWithHistoryAndExpansion() {
    open("04")
    composeRule.onNodeWithText("Запустить сравнение").performScrollTo().performClick()
    composeRule.waitUntil { temperatureCalls == 1 }
    back()
    open("02")
    composeRule.onNodeWithText("Запрос").performTextReplacement("Отдельный запрос второго дня")
    Espresso.closeSoftKeyboard()
    composeRule.activityRule.scenario.recreate()
    composeRule.runOnIdle { temperatureResult.complete(temperatureBatch()) }
    back()
    open("04")
    composeRule.waitUntil { !temperature.uiState.value.isLoading }
    composeRule.onNodeWithText("Показать ответ").performScrollTo().performClick()
    composeRule.onNodeWithText("Ответ температуры").performScrollTo().assertIsDisplayed()
    val scroll = scrollPosition("lesson_04")
    back()
    open("03")
    back()
    open("04")
    assertEquals(scroll, scrollPosition("lesson_04"), 1f)
    composeRule.onNodeWithText("Ответ температуры").assertIsDisplayed()
    composeRule.activityRule.scenario.recreate()
    composeRule.onNodeWithText("Ответ температуры").assertIsDisplayed()
    composeRule.onNodeWithText("История текущего запроса").performScrollTo().assertIsDisplayed()
    composeRule.runOnIdle {
      assertEquals(1, temperatureCalls)
      assertEquals("temperature-test", temperature.uiState.value.history.single().request_id)
      assertEquals(CANONICAL_TEMPERATURE_PROMPT, temperature.uiState.value.prompt)
      assertEquals("Отдельный запрос второго дня", response.uiState.value.prompt)
    }
  }

  @Test
  fun failedRequestRemainsVisibleAfterRoundTripWithoutRetry() {
    open("04")
    composeRule.onNodeWithText("Запустить сравнение").performScrollTo().performClick()
    composeRule.waitUntil { temperatureCalls == 1 }
    back()
    composeRule.runOnIdle { temperatureResult.completeExceptionally(IllegalStateException("offline")) }
    open("04")
    composeRule.onNodeWithText("Ошибка запуска:", substring = true).performScrollTo().assertIsDisplayed()
    back()
    open("04")
    composeRule.onNodeWithText("Ошибка запуска:", substring = true).assertIsDisplayed()
    composeRule.runOnIdle { assertEquals(1, temperatureCalls) }
  }

  @Test
  fun reasoningExpansionAndCatalogScrollSurviveRoundTrip() {
    // Scroll also works when the current device needs only a short catalog.
    composeRule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_04"))
    val homeScroll = scrollPosition("days_catalog")
    open("04")
    back()
    assertEquals(homeScroll, scrollPosition("days_catalog"), 1f)
    open("03")
    composeRule.onNodeWithText("Запустить все стратегии").performScrollTo().performClick()
    composeRule.onNodeWithText("Показать сгенерированный промпт").performScrollTo().performClick()
    composeRule.onNodeWithText("Сохранённый мета-промпт").performScrollTo().assertIsDisplayed()
    val scroll = scrollPosition("lesson_03")
    back()
    open("03")
    assertEquals(scroll, scrollPosition("lesson_03"), 1f)
    composeRule.onNodeWithText("Сохранённый мета-промпт").assertIsDisplayed()
    composeRule.runOnIdle { assertEquals(1, reasoningCalls) }
  }

  @Test
  fun systemBackClosesKeyboardBeforeLeavingDay() {
    open("02")
    composeRule.onNodeWithText("Запрос").performClick()
    composeRule.waitForIdle()
    Espresso.pressBack()
    composeRule.onNodeWithText("День 02").assertIsDisplayed()
    Espresso.pressBack()
    composeRule.onNodeWithText("AI Advent").assertIsDisplayed()
  }

  private fun open(day: String) {
    composeRule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_$day"))
    composeRule.onNodeWithTag("day_$day").performClick()
  }

  private fun back() {
    composeRule.onNodeWithContentDescription("Назад к дням").performClick()
    composeRule.onNodeWithText("AI Advent").assertIsDisplayed()
  }

  private fun scrollPosition(tag: String): Float =
    composeRule.onNodeWithTag(tag).fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
}

private fun temperatureBatch() = TemperatureLabBatchResponseDto(
  request_id = "temperature-test",
  mode = "benchmark",
  mode_message = "",
  config = TemperatureExperimentConfigDto(
    model = "test-model", temperatures = listOf(0.0, 0.7, 1.2),
    reasoning_effort = "none", reasoning_mode = "standard", max_output_tokens = 600,
    top_p = "default", prompt_cache_mode = "disabled", output_contract = "variants",
    temperature_only_variable = true,
  ),
  results = listOf(
    TemperatureResultDto(
      temperature = 0.0, status = "completed", latency_ms = 10,
      usage = TokenUsageDto(10, 10, 0, 20), content = "Ответ температуры",
    )
  ),
)
