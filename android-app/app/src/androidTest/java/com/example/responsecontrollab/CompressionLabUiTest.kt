package com.example.responsecontrollab

import android.content.pm.ActivityInfo
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.compression.*
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CompressionLabUiTest {
  @get:Rule val rule = createAndroidComposeRule<MainActivity>()
  private val repo = CompressionUiRepository()
  private lateinit var vm: CompressionLabViewModel
  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm = ViewModelProvider(activity, CompressionLabViewModel.factory(repo, tokenUiStore()))[CompressionLabViewModel.KEY, CompressionLabViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    open()
  }
  private fun open() {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_09"))
    rule.onNodeWithTag("day_09").performClick()
    rule.waitUntil { vm.uiState.value.ready }
  }
  private fun reveal(tag: String) = rule.onNodeWithTag("compression_stats").performScrollToNode(hasTestTag(tag))
  private fun send() {
    rule.onNodeWithTag("compression_input").performTextInput("Контрольный запрос")
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("compression_send").performClick()
    rule.waitUntil { vm.uiState.value.historyTurnCount == 1 }
  }
  @Test fun compactChatAndNestedBackRetainDraftAndObservationsWithoutReplay() {
    rule.onNodeWithTag("compression_delta").assertTextEquals("Изменение: ещё не измерено")
    rule.onNodeWithTag("compression_stats").assertDoesNotExist()
    send()
    rule.onNodeWithTag("compression_delta").assertTextEquals("Дополнительный расход: 20 токенов (+20.0%)")
    rule.onNodeWithText("DURABLE summary").assertDoesNotExist()
    rule.onNodeWithTag("compression_input").performTextInput("Неотправленный черновик")
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("compression_details").performClick()
    reveal("compression_summary_toggle")
    rule.onNodeWithTag("compression_summary_toggle").performClick()
    rule.onNodeWithTag("compression_durable_summary").assertTextEquals("DURABLE summary")
    rule.activityRule.scenario.recreate()
    rule.onNodeWithTag("compression_durable_summary").assertIsDisplayed()
    rule.onNodeWithTag("compression_details_back").performClick()
    rule.onNodeWithTag("compression_input").assertTextContains("Неотправленный черновик")
    rule.onNodeWithTag("compression_details").performClick()
    Espresso.pressBack()
    rule.onNodeWithTag("compression_details").assertIsDisplayed()
    Espresso.pressBack()
    rule.onNodeWithText("AI Advent").assertIsDisplayed()
    open()
    rule.runOnIdle { assertEquals(1, repo.sends); assertEquals(0, repo.compares); assertEquals(1, vm.uiState.value.observations.size) }
  }
  @Test fun visibleFixtureIsOnlyDraftAndKeyboardBackStaysInChat() {
    rule.onNodeWithTag("compression_fixture").performClick()
    rule.runOnIdle { assertEquals(CompressionScenario.messages()[0], vm.uiState.value.draft); assertEquals(0, repo.creates); assertEquals(0, repo.sends) }
    rule.onNodeWithText("Прочитать учебный текст целиком").performClick()
    rule.onNodeWithText("Текст перед отправкой").assertIsDisplayed()
    rule.onNodeWithText("Закрыть").performClick()
    rule.onNodeWithTag("compression_input").performClick()
    rule.waitForIdle()
    Espresso.pressBack()
    rule.onNodeWithText("День 09").assertIsDisplayed()
    rule.onNodeWithTag("compression_reset").performClick()
    rule.waitUntil { vm.uiState.value.draft.isEmpty() }
  }
  @Test fun explicitCompareShowsPartialFailureAndAdaptsToWideWindow() {
    send()
    rule.onNodeWithTag("compression_details").performClick()
    reveal("compression_compare_scored")
    rule.onNodeWithTag("compression_compare_scored").performClick()
    rule.waitUntil { vm.uiState.value.comparison != null }
    reveal("compression_vertical")
    rule.onNodeWithText("Проверка трёх фактов: 3/3").assertExists()
    rule.onNodeWithText("Проверка трёх фактов: нет оценки").assertExists()
    rule.runOnIdle { assertEquals(1, repo.compares); assertEquals(2, vm.uiState.value.messages.size); assertEquals("DURABLE summary", vm.uiState.value.summary?.text) }
    try {
      rule.activityRule.scenario.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE }
      rule.waitUntil(10000) { rule.onAllNodesWithTag("compression_side_by_side").fetchSemanticsNodes().isNotEmpty() }
      reveal("compression_side_by_side")
      rule.onNodeWithTag("compression_side_by_side").assertExists()
      rule.runOnIdle { assertEquals(1, repo.compares) }
    } finally { rule.activityRule.scenario.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED } }
  }

}

internal class CompressionUiRepository : CompressionLabRepository {
  var creates = 0; var sends = 0; var compares = 0; private var count = 0
  private val id = "99999999-9999-4999-8999-999999999999"
  private val summary = CompressionSummaryDto(id, "DURABLE summary", 1, COMPRESSION_VERSION)
  override suspend fun create(): CompressionSessionDto { creates++; return CompressionSessionDto(id, count) }
  override suspend fun get(id: String) = CompressionSessionDto(id, count)
  override suspend fun summary(id: String) = summary
  override suspend fun delete(id: String) { count = 0 }
  override suspend fun send(id: String, message: String): CompressionOperationDto {
    sends++; count++
    return CompressionOperationDto(id, count, "r", "send-$sends", status = "completed", committed = true, reply = "Принято",
      context = CompressionContextDto(fullInputTokens = 100, compressedInputTokens = 120, tokenDelta = -20, percentDelta = -20.0, rawTailCount = 0),
      durableSummary = summary, summarySource = "durable")
  }
  override suspend fun compare(id: String, question: String, scenarioId: String?): CompressionOperationDto {
    compares++
    return CompressionOperationDto(id, count, "r", "compare-$compares", kind = "compare", status = "partial", question = question,
      durableSummary = summary, compareSummary = summary.copy(text = "LOCAL summary", boundary = 3), summarySource = "compare_local",
      full = CompressionBranchDto(status = "completed", reply = "identifier=ORBIT-7319\nlimit=37\nresponsible=Мира", score = 3),
      compressed = CompressionBranchDto(status = "error", errorCode = "provider_error"), scenarioStatus = "applicable")
  }
}
