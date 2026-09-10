package com.example.responsecontrollab

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.token.TokenLabViewModel
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class TokenLabUiTest {
  @get:Rule val rule = createAndroidComposeRule<MainActivity>()
  private val repo = TokenUiRepository()
  private lateinit var vm: TokenLabViewModel

  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm = ViewModelProvider(activity, TokenLabViewModel.factory(repo, tokenUiStore()))[TokenLabViewModel.KEY, TokenLabViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    open()
  }
  private fun open() {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_08"))
    rule.onNodeWithTag("day_08").performClick()
    rule.waitUntil { vm.uiState.value.initialized && !vm.uiState.value.busy }
  }
  private fun reveal(tag: String) {
    rule.onNodeWithTag("token_content").performScrollToNode(hasTestTag(tag))
  }

  @Test fun normalSendDisplaysIndependentCountsAndKeepsStateAfterRecreation() {
    rule.runOnIdle { assertEquals(0, repo.creates) }
    rule.onNodeWithTag("token_input").performTextInput("Короткий вопрос")
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("token_send").performClick()
    rule.waitUntil { vm.uiState.value.historyTurnCount == 1 }
    reveal("token_actual_input")
    rule.onNodeWithTag("token_actual_input").assertTextEquals("Actual API input: 45")
    reveal("token_preflight")
    rule.onNodeWithTag("token_preflight").assertTextEquals("Preflight input модели: 40")
    reveal("token_cost")
    rule.onNodeWithTag("token_cost").assertTextEquals("Оценочная стоимость хода: 0.000195 USD")
    rule.activityRule.scenario.recreate()
    rule.onNodeWithText("День 08").assertIsDisplayed()
    rule.runOnIdle { assertEquals(1, repo.sends); assertEquals(1, vm.uiState.value.observations.size) }
    rule.onNodeWithContentDescription("Назад к дням").performClick()
    open()
    rule.runOnIdle { assertEquals(1, repo.sends) }
  }

  @Test fun overflowRequiresSeparateConfirmationAndPreservesUnknownUsage() {
    reveal("token_prepare")
    rule.onNodeWithTag("token_prepare").performClick()
    rule.waitUntil { vm.uiState.value.preparation != null }
    rule.runOnIdle { assertEquals(0, repo.executes); assertEquals(0, repo.sends) }
    reveal("token_execute")
    rule.onNodeWithTag("token_execute").performClick()
    rule.runOnIdle { assertEquals(0, repo.executes) }
    rule.onNodeWithTag("token_confirm").performClick()
    rule.waitUntil { vm.uiState.value.lastAttempt?.error?.code == "context_limit_exceeded" }
    reveal("token_actual_input")
    rule.onNodeWithTag("token_actual_input").assertTextEquals("Actual API input: нет данных")
    reveal("token_cost")
    rule.onNodeWithTag("token_cost").assertTextEquals("Оценочная стоимость хода: нет данных")
    rule.onNodeWithText("Завершённых ходов: 0").assertIsDisplayed()
    rule.runOnIdle { assertEquals(1, repo.executes); assertTrue(vm.uiState.value.ready) }
  }

  @Test fun longFixtureRequiresExplicitSendAndResetClearsOnlyRuntimeState() {
    reveal("token_long"); rule.onNodeWithTag("token_long").performClick()
    rule.runOnIdle { assertTrue(vm.uiState.value.draft.length <= 20000); assertEquals(0, repo.sends) }
    rule.onNodeWithTag("token_reset").performClick()
    rule.waitUntil { vm.uiState.value.draft.isEmpty() }
    rule.runOnIdle { assertEquals(0, repo.creates); assertTrue(vm.uiState.value.observations.isEmpty()) }
  }
}

internal fun tokenUiStore() = object : CurrentSessionStore {
  private var id: String? = null
  override suspend fun read() = id
  override suspend fun save(sessionId: String) { id = sessionId }
  override suspend fun clear() { id = null }
}

internal class TokenUiRepository : TokenLabRepository {
  var creates = 0
  var sends = 0
  var executes = 0
  var count = 0
  private val id = "11111111-1111-4111-8111-111111111111"
  override suspend fun create(): ChatSessionDto { creates++; return ChatSessionDto(id, count) }
  override suspend fun get(id: String) = ChatSessionDto(id, count)
  override suspend fun delete(id: String) { count = 0 }
  private fun result(status: String, committed: Boolean = false) = TokenTurnDto(id, count, "r", "a-$status-$count", status,
    reply = if (committed) "Краткий ответ" else null, committed = committed, generationAttempted = committed,
    diagnostics = TokenDiagnosticsDto(currentMessageTokens = 12, savedHistoryTokens = 31, preflightInputTokens = 40,
      contextWindow = 128000, reservedOutputTokens = 1200, countCalls = 3))
  override suspend fun send(id: String, message: String): TokenTurnDto {
    sends++; count++
    return result("completed", true).copy(usage = TokenLabUsageDto(inputTokens = 45, outputTokens = 10),
      cost = TokenCostDto(status = "available", amountUsd = "0.000195"))
  }
  override suspend fun prepare(id: String) = result("prepared").copy(
    diagnostics = TokenDiagnosticsDto(preflightInputTokens = 139902, contextWindow = 128000,
      reservedOutputTokens = 1200, countCalls = 2, reserveWarning = true),
    preparation = OverflowPreparationDto("p", "gpt-4o-mini", "v1", 13975, "0123456789 abcdefghijklmnopqrstuvwxyz\n",
      "Тест контекста", "Ответь кратко: принято", 531149, 531228, 546130, "sha", "start", "end", 0.0,
      System.currentTimeMillis()/1000.0+600))
  override suspend fun execute(id: String, preparationId: String): TokenTurnDto {
    executes++
    return result("error").copy(generationAttempted = true,
      error = ChatErrorDto("context_limit_exceeded", "Модель отклонила запрос: превышено окно контекста."),
      errorOrigin = "provider", diagnostics = prepare(id).diagnostics)
  }
}
