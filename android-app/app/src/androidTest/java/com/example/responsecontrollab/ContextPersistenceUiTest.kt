package com.example.responsecontrollab

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
class ContextPersistenceUiTest {
  @get:Rule val rule = createAndroidComposeRule<MainActivity>()
  private val fake = PersistentUiFixture()
  private val day06Fake = PersistentUiFixture()
  private lateinit var vm: ChatViewModel

  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm = ViewModelProvider(activity, ChatViewModel.factory(fake, fake))[ChatViewModel.DAY_07_KEY, ChatViewModel::class.java]
      ViewModelProvider(activity, ChatViewModel.factory(day06Fake))[ChatViewModel.DAY_06_KEY, ChatViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    rule.runOnIdle { assertTrue(fake.calls.isEmpty()) }
  }

  @Test fun restoredMetadataShowsNoticeAndOnlyNewTranscriptThenReset() {
    open("07")
    rule.waitUntil { vm.uiState.value.restored }
    rule.onNodeWithText("Сохранение контекста").assertIsDisplayed()
    rule.onNodeWithText("Завершённых ходов: 1").assertIsDisplayed()
    rule.onNodeWithTag("chat_restored").assertIsDisplayed()
    rule.onNodeWithTag("chat_message_0").assertDoesNotExist()
    send("Какой факт?")
    rule.onNodeWithText("Завершённых ходов: 2").assertIsDisplayed()
    rule.onNodeWithText("Ответ 2").assertIsDisplayed()
    rule.runOnIdle { assertEquals(listOf("read", "get", "send:Какой факт?"), fake.calls) }
    rule.onNodeWithTag("chat_reset").performClick()
    rule.waitUntil { vm.uiState.value.sessionId == null }
    rule.onNodeWithTag("chat_restored").assertDoesNotExist()
    rule.onNodeWithText("Завершённых ходов: 0").assertIsDisplayed()
    rule.runOnIdle { assertNull(fake.saved); assertEquals(listOf("delete", "clear"), fake.calls.takeLast(2)) }
  }

  @Test fun restoreInFlightSurvivesNavigationAndRecreationWithSeparateDay06Draft() {
    fake.getGate = CompletableDeferred()
    open("07")
    rule.waitUntil { fake.calls.contains("get") }
    rule.onNodeWithText("Восстанавливаем диалог…").assertIsDisplayed()
    rule.onNodeWithText("История диалога пока не подтверждена").assertIsDisplayed()
    rule.onNodeWithTag("chat_send").assertIsNotEnabled()
    back(); open("06")
    rule.onNodeWithText("Первый агент").assertIsDisplayed()
    rule.onNodeWithTag("chat_input").performTextReplacement("Day 06 draft")
    Espresso.closeSoftKeyboard()
    rule.activityRule.scenario.recreate()
    rule.runOnIdle { fake.getGate!!.complete(Unit) }
    back(); open("07")
    rule.waitUntil { vm.uiState.value.restored }
    rule.onNodeWithTag("chat_input").assertTextContains("")
    rule.activityRule.scenario.recreate()
    rule.runOnIdle { assertEquals(listOf("read", "get"), fake.calls); assertTrue(day06Fake.calls.isEmpty()) }
    back(); open("06")
    rule.onNodeWithTag("chat_input").assertTextContains("Day 06 draft")
  }

  @Test fun failedRestoreOffersExplicitRetryAndMissingSessionOffersReset() {
    fake.getError = "unknown"
    open("07")
    rule.waitUntil { vm.uiState.value.canRetryRestore }
    rule.onNodeWithTag("chat_error").assertIsDisplayed()
    rule.onNodeWithTag("chat_send").assertIsNotEnabled()
    back(); open("07")
    rule.runOnIdle { assertEquals(listOf("read", "get"), fake.calls); fake.getError = "session_not_found" }
    rule.onNodeWithTag("chat_restore_retry").performClick()
    rule.waitUntil { vm.uiState.value.recoveryRequired }
    rule.onNodeWithText("Диалог недоступен. Начните новый диалог.").assertIsDisplayed()
    rule.onNodeWithTag("chat_restore_retry").assertDoesNotExist()
    rule.onNodeWithTag("chat_reset").assertIsEnabled().performClick()
    rule.waitUntil { vm.uiState.value.sessionId == null }
    rule.runOnIdle { assertNull(fake.saved) }
  }

  @Test fun noIdIsEmptyAndLongContentScrollAndActionsSurviveVisits() {
    fake.saved = null; fake.count = 0; fake.longReply = true
    open("07")
    rule.waitUntil { vm.uiState.value.identityKnown }
    rule.onNodeWithTag("chat_restored").assertDoesNotExist()
    rule.runOnIdle { assertEquals(listOf("read"), fake.calls) }
    rule.onNodeWithTag("chat_input").performTextReplacement("Длинный текст ".repeat(40))
    // Check actions with the IME, then use the same viewport for both scroll measurements.
    rule.onNodeWithTag("chat_send").assertIsDisplayed()
    rule.onNodeWithTag("chat_reset").assertIsDisplayed()
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("chat_send").performClick()
    rule.waitUntil { !vm.uiState.value.busy }
    // Stay in the middle of a long bubble: an end-of-list offset is clamped
    // while Activity window insets are reapplied to a temporarily taller viewport.
    rule.onNodeWithTag("chat_transcript").performTouchInput { swipeUp() }
    val position = scroll()
    assertTrue(position > 0f)
    back(); open("06"); back(); open("07")
    assertEquals(position, scroll(), 1f)
    rule.activityRule.scenario.recreate()
    assertEquals(position, scroll(), 1f)
    rule.onNodeWithTag("chat_reset").assertIsDisplayed().performClick()
    rule.waitUntil { vm.uiState.value.sessionId == null }
    rule.activityRule.scenario.recreate()
    rule.runOnIdle {
      assertEquals(1, fake.calls.count { it == "create" })
      assertEquals(1, fake.calls.count { it == "save" })
      assertEquals(1, fake.calls.count { it == "delete" })
      assertEquals(0, fake.calls.count { it == "get" })
    }
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
  // LazyColumn scroll semantics estimate total distance from measured item sizes.
  // Compare the actual visible bubble anchor across recreation instead.
  private fun scroll() = -rule.onNodeWithTag("chat_message_1").fetchSemanticsNode().positionInRoot.y
}

private class PersistentUiFixture : ChatRepository, CurrentSessionStore {
  private val id = "b346265c-d546-4b9e-aeb8-a5cde44f4474"
  var saved: String? = id
  var count = 1
  var getError: String? = null
  var getGate: CompletableDeferred<Unit>? = null
  var longReply = false
  val calls = mutableListOf<String>()
  override suspend fun read(): String? { calls += "read"; return saved }
  override suspend fun save(sessionId: String) { calls += "save"; saved = sessionId }
  override suspend fun clear() { calls += "clear"; saved = null }
  override suspend fun createSession(): ChatSessionDto { calls += "create"; return ChatSessionDto(id, 0) }
  override suspend fun getSession(sessionId: String): ChatSessionDto {
    check(sessionId == id); calls += "get"; getGate?.await()
    getError?.let { throw ChatRequestException(it, "error") }
    return ChatSessionDto(id, count)
  }
  override suspend fun sendMessage(sessionId: String, message: String): ChatTurnDto {
    check(sessionId == id); calls += "send:$message"; count++
    return ChatTurnDto(id, "r", "completed", if (longReply) "Длинный ответ. ".repeat(300) else "Ответ $count", count, null, null)
  }
  override suspend fun deleteSession(sessionId: String) { check(sessionId == id); calls += "delete" }
}
