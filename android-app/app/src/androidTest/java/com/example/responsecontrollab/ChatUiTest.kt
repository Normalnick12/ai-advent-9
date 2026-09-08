package com.example.responsecontrollab

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.chat.ChatViewModel
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ChatUiTest {
  @get:Rule val rule = createAndroidComposeRule<MainActivity>()
  private val repo = UiChatRepository()
  private lateinit var vm: ChatViewModel

  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm = ViewModelProvider(activity, ChatViewModel.factory(repo))[ChatViewModel.DAY_06_KEY, ChatViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    open("06")
  }

  @Test fun sendsActualReplyAndResetsWithoutEagerCreation() {
    rule.runOnIdle { assertTrue(repo.calls.isEmpty()) }
    send("Факт")
    rule.onNodeWithText("Ответ агента 1").assertIsDisplayed()
    rule.onNodeWithText("Завершённых ходов: 1").assertIsDisplayed()
    send("Вопрос")
    rule.onNodeWithTag("chat_transcript").performScrollToNode(hasText("Ответ агента 2"))
    rule.onNodeWithText("Ответ агента 2").assertIsDisplayed()
    rule.onNodeWithTag("chat_reset").performClick()
    rule.waitUntil { vm.uiState.value.sessionId == null }
    rule.onNodeWithText("Завершённых ходов: 0").assertIsDisplayed()
    rule.onNodeWithText("Ответ агента 1").assertDoesNotExist()
    rule.runOnIdle { assertEquals(listOf("create", "send:s1:Факт", "send:s1:Вопрос", "delete:s1"), repo.calls) }
    send("Без факта")
    rule.runOnIdle { assertEquals("send:s2:Без факта", repo.calls.last()) }
  }

  @Test fun incompleteRefusalAndLostSessionAreExplicit() {
    for (status in listOf("incomplete", "refused", "session_not_found")) {
      rule.runOnIdle { repo.outcome = status }
      send("Вопрос")
      rule.onNodeWithTag("chat_transcript").performScrollToNode(hasTestTag("chat_error"))
      rule.onNodeWithTag("chat_error").assertIsDisplayed()
      rule.onNodeWithText("Завершённых ходов: 0").assertIsDisplayed()
      if (status == "session_not_found") {
        rule.onNodeWithTag("chat_send").assertIsNotEnabled()
        rule.onNodeWithText("Диалог недоступен. Начните новый диалог.").assertIsDisplayed()
      }
    }
  }

  @Test fun pendingTurnSurvivesAnotherDayAndRecreationWithoutDuplicateCalls() {
    rule.runOnIdle { repo.gate = CompletableDeferred() }
    rule.onNodeWithTag("chat_input").performTextReplacement("Сохрани факт")
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("chat_send").performClick()
    rule.waitUntil { repo.calls.size == 2 }
    rule.onNodeWithTag("chat_pending").assertIsDisplayed()
    rule.onNodeWithTag("chat_reset").assertIsNotEnabled()
    back(); open("02")
    rule.activityRule.scenario.recreate()
    rule.runOnIdle { repo.gate!!.complete(Unit) }
    back(); open("06")
    rule.onNodeWithText("Ответ агента 1").assertIsDisplayed()
    rule.runOnIdle { assertEquals(listOf("create", "send:s1:Сохрани факт"), repo.calls) }
    rule.onNodeWithTag("chat_input").performTextReplacement("Черновик")
    Espresso.closeSoftKeyboard()
    rule.activityRule.scenario.recreate()
    rule.onNodeWithTag("chat_input").assertTextContains("Черновик")
  }

  @Test fun longTranscriptScrollSurvivesVisitsAndResetClearsIt() {
    rule.runOnIdle { repo.longReply = true }
    send("Длинное сообщение ".repeat(30))
    rule.onNodeWithTag("chat_transcript").performTouchInput { swipeUp() }
    val before = scroll()
    assertTrue(before > 0f)
    back(); open("02"); back(); open("06")
    assertEquals(before, scroll(), 1f)
    rule.activityRule.scenario.recreate()
    assertEquals(before, scroll(), 1f)
    rule.onNodeWithTag("chat_reset").performClick()
    rule.waitUntil { vm.uiState.value.sessionId == null }
    assertEquals(0f, scroll(), 1f)
  }

  private fun send(text: String) {
    rule.onNodeWithTag("chat_input").performTextReplacement(text)
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("chat_send").performClick()
    rule.waitUntil { !vm.uiState.value.busy }
  }
  private fun open(day: String) {
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_$day"))
    rule.onNodeWithTag("day_$day").performClick()
  }
  private fun back() { rule.onNodeWithContentDescription("Назад к дням").performClick() }
  private fun scroll() = rule.onNodeWithTag("chat_transcript").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange].value()
}

private class UiChatRepository : ChatRepository {
  val calls = mutableListOf<String>()
  var gate: CompletableDeferred<Unit>? = null
  var outcome = "completed"
  var longReply = false
  private var sessions = 0
  private var count = 0
  override suspend fun getSession(sessionId: String): ChatSessionDto = error("Unexpected GET")
  override suspend fun createSession(): ChatSessionDto {
    calls += "create"; sessions++; count = 0
    return ChatSessionDto("s$sessions", 0)
  }
  override suspend fun sendMessage(sessionId: String, message: String): ChatTurnDto {
    calls += "send:$sessionId:$message"
    gate?.await()
    if (outcome == "session_not_found") throw ChatRequestException(outcome, "Диалог потерян")
    if (outcome == "completed") count++
    return ChatTurnDto(sessionId, "r", outcome,
      if (outcome == "completed") if (longReply) "Длинный ответ агента. ".repeat(150) else "Ответ агента $count" else null,
      count, null, if (outcome == "completed") null else ChatErrorDto("llm_$outcome", if (outcome == "refused") "Модель отказалась отвечать на запрос." else "Ответ модели не завершён."))
  }
  override suspend fun deleteSession(sessionId: String) { calls += "delete:$sessionId" }
}
