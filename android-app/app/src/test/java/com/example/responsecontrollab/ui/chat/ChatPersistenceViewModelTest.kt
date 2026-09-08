package com.example.responsecontrollab.ui.chat

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatPersistenceViewModelTest {
  @get:Rule val dispatcher = MainDispatcherRule()

  @Test fun entryWithNoIdDoesNotCreateAndSaveMustFinishBeforeSend() = runTest {
    val f = Fixture()
    val vm = f.vm()
    assertTrue(f.calls.isEmpty())
    vm.initialize(); advanceUntilIdle()
    assertEquals(listOf("read"), f.calls)
    f.saveGate = CompletableDeferred()
    vm.updateDraft(" U1\n😀 "); vm.send(); runCurrent()
    assertEquals(listOf("read", "create", "save"), f.calls)
    assertEquals(ChatOperation.SAVING_ID, vm.uiState.value.operation)
    assertFalse(vm.uiState.value.canSend)
    f.saveGate!!.complete(Unit); advanceUntilIdle()
    assertEquals(listOf("read", "create", "save", "send: U1\n😀 "), f.calls)
    assertEquals(ID, f.saved)
    assertEquals(1, vm.uiState.value.historyTurnCount)
  }

  @Test fun saveFailureKeepsDraftAndRetriesSameIdentityWithoutCreate() = runTest {
    val f = Fixture().apply { saveFails = true }
    val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("U1"); vm.send(); advanceUntilIdle()
    assertEquals(ID, vm.uiState.value.sessionId)
    assertEquals("U1", vm.uiState.value.draft)
    assertEquals(0, vm.uiState.value.historyTurnCount)
    assertTrue(vm.uiState.value.messages.isEmpty())
    assertFalse(vm.uiState.value.recoveryRequired)
    assertNull(f.saved)
    f.saveFails = false
    vm.send(); advanceUntilIdle()
    assertEquals(listOf("read", "create", "save", "save", "send:U1"), f.calls)
  }

  @Test fun coldStartRestoresOnlyIdAndCountAndNextSendOnlyNewText() = runTest {
    val f = Fixture().apply { saved = ID; count = 1; getGate = CompletableDeferred() }
    val vm = f.vm(); vm.updateDraft("U2"); vm.initialize(); runCurrent()
    assertNull(vm.uiState.value.historyTurnCount)
    assertFalse(vm.uiState.value.canSend)
    vm.send(); vm.initialize(); runCurrent()
    assertEquals(listOf("read", "get"), f.calls)
    f.getGate!!.complete(Unit); advanceUntilIdle()
    assertEquals(ID, vm.uiState.value.sessionId)
    assertEquals(1, vm.uiState.value.historyTurnCount)
    assertTrue(vm.uiState.value.messages.isEmpty())
    assertTrue(vm.uiState.value.restored)
    vm.initialize(); vm.send(); advanceUntilIdle()
    assertEquals(listOf("read", "get", "send:U2"), f.calls)
    assertEquals(listOf("U2", "A2"), vm.uiState.value.messages.map { it.text })
    assertEquals(2, vm.uiState.value.historyTurnCount)
  }

  @Test fun localReadFailureBlocksResetAndSendUntilExplicitRetry() = runTest {
    val f = Fixture().apply { readFails = true; saved = ID }
    val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("U"); vm.send(); vm.newConversation(); vm.initialize(); advanceUntilIdle()
    assertEquals(listOf("read"), f.calls)
    assertFalse(vm.uiState.value.canReset)
    assertTrue(vm.uiState.value.canRetryRestore)
    f.readFails = false; vm.retryRestore(); advanceUntilIdle()
    assertEquals(listOf("read", "read", "get"), f.calls)
    assertTrue(vm.uiState.value.canSend)
  }

  @Test fun metadataErrorsNeverCreateOrReplayAndRetryIsExplicit() = runTest {
    for (code in listOf("unknown", "session_busy", "validation_error")) {
      val f = Fixture().apply { saved = ID; getError = code }
      val vm = f.vm(); vm.initialize(); advanceUntilIdle()
      vm.updateDraft("U"); vm.send(); vm.initialize(); advanceUntilIdle()
      assertEquals(listOf("read", "get"), f.calls)
      assertNull(vm.uiState.value.historyTurnCount)
      assertTrue(vm.uiState.value.canRetryRestore)
      f.getError = null; vm.retryRestore(); advanceUntilIdle()
      assertEquals(listOf("read", "get", "get"), f.calls)
      assertTrue(vm.uiState.value.canSend)
    }
  }

  @Test fun missingSessionRequiresResetAndMalformedLocalIdOnlyClearsLocalStore() = runTest {
    for (id in listOf(ID, "invalid")) {
      val f = Fixture().apply { saved = id; getError = "session_not_found" }
      val vm = f.vm(); vm.initialize(); advanceUntilIdle()
      assertTrue(vm.uiState.value.recoveryRequired)
      assertFalse(vm.uiState.value.canRetryRestore)
      assertEquals(id, f.saved)
      vm.newConversation(); advanceUntilIdle()
      assertNull(f.saved)
      assertNull(vm.uiState.value.sessionId)
      assertEquals(if (id == ID) listOf("read", "get", "delete", "clear") else listOf("read", "clear"), f.calls)
    }
  }

  @Test fun resetDeletesThenClearsBeforeResettingUiAndSurvivesColdStart() = runTest {
    val f = Fixture().apply { saved = ID; count = 1; clearGate = CompletableDeferred() }
    val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("draft"); vm.newConversation(); runCurrent()
    assertEquals(listOf("read", "get", "delete", "clear"), f.calls)
    assertEquals(ID, vm.uiState.value.sessionId)
    assertEquals("draft", vm.uiState.value.draft)
    assertTrue(vm.uiState.value.busy)
    f.clearGate!!.complete(Unit); advanceUntilIdle()
    assertNull(f.saved)
    assertEquals(0, vm.uiState.value.historyTurnCount)
    val next = f.vm(); next.initialize(); advanceUntilIdle()
    assertNull(next.uiState.value.sessionId)
    assertEquals("read", f.calls.last())
  }

  @Test fun failedDeleteOrClearDoesNotClaimResetAndRetryIsIdempotent() = runTest {
    for (deleteFailure in listOf(true, false)) {
      val f = Fixture().apply { saved = ID; count = 1; deleteFails = deleteFailure; clearFails = !deleteFailure }
      val vm = f.vm(); vm.initialize(); advanceUntilIdle()
      vm.updateDraft("draft"); vm.newConversation(); advanceUntilIdle()
      assertEquals(ID, f.saved)
      assertEquals(ID, vm.uiState.value.sessionId)
      assertEquals(1, vm.uiState.value.historyTurnCount)
      assertEquals("draft", vm.uiState.value.draft)
      assertTrue(vm.uiState.value.recoveryRequired)
      assertEquals(if (deleteFailure) "delete" else "clear", f.calls.last())
      f.deleteFails = false; f.clearFails = false
      vm.newConversation(); advanceUntilIdle()
      assertNull(f.saved)
      assertNull(vm.uiState.value.sessionId)
      assertEquals(2, f.calls.count { it == "delete" })
    }
  }

  @Test fun newRuntimeDoesNotRestorePendingOrUnknownOutcomeAndNeverAutoReplays() = runTest {
    val f = Fixture().apply { saved = ID; count = 1; sendError = "unknown" }
    val old = f.vm(); old.initialize(); advanceUntilIdle()
    old.updateDraft("uncertain"); old.send(); advanceUntilIdle()
    assertTrue(old.uiState.value.recoveryRequired)
    val fresh = f.vm(); fresh.initialize(); advanceUntilIdle()
    assertFalse(fresh.uiState.value.recoveryRequired)
    assertNull(fresh.uiState.value.pendingUser)
    assertTrue(fresh.uiState.value.messages.isEmpty())
    assertEquals("", fresh.uiState.value.draft)
    assertEquals(1, f.calls.count { it.startsWith("send:") })
  }

  @Test fun day06AndDay07HaveIndependentDraftIdentityTranscriptAndOperations() = runTest {
    val f = Fixture().apply { saved = ID; count = 1 }
    val persistent = f.vm(); persistent.initialize(); advanceUntilIdle()
    persistent.updateDraft("day07")
    val other = Fixture("331eb1c8-3b6e-4e2a-9c7a-3cbdf8fb7285").apply { sendGate = CompletableDeferred() }
    val day06 = ChatViewModel(other)
    day06.updateDraft("day06"); day06.send(); runCurrent()
    assertTrue(day06.uiState.value.busy)
    assertFalse(persistent.uiState.value.busy)
    assertNotEquals(persistent.uiState.value.sessionId, day06.uiState.value.sessionId)
    other.sendGate!!.complete(Unit); advanceUntilIdle()
    assertEquals("day07", persistent.uiState.value.draft)
    assertTrue(persistent.uiState.value.messages.isEmpty())
    assertEquals(listOf("create", "send:day06"), other.calls)
    day06.newConversation(); advanceUntilIdle()
    assertEquals(ID, persistent.uiState.value.sessionId)
    assertEquals(ID, f.saved)
    assertEquals(listOf("read", "get"), f.calls)
  }
}

private const val ID = "b346265c-d546-4b9e-aeb8-a5cde44f4474"
private class Fixture(private val id: String = ID) : ChatRepository, CurrentSessionStore {
  val calls = mutableListOf<String>()
  var saved: String? = null
  var count = 0
  var readFails = false
  var saveFails = false
  var clearFails = false
  var deleteFails = false
  var getError: String? = null
  var sendError: String? = null
  var sendGate: CompletableDeferred<Unit>? = null
  var saveGate: CompletableDeferred<Unit>? = null
  var clearGate: CompletableDeferred<Unit>? = null
  var getGate: CompletableDeferred<Unit>? = null
  fun vm() = ChatViewModel(this, this)
  override suspend fun read(): String? { calls += "read"; check(!readFails); return saved }
  override suspend fun save(sessionId: String) { calls += "save"; saveGate?.await(); check(!saveFails); saved = sessionId }
  override suspend fun clear() { calls += "clear"; clearGate?.await(); check(!clearFails); saved = null }
  override suspend fun createSession(): ChatSessionDto { calls += "create"; return ChatSessionDto(id, 0) }
  override suspend fun getSession(sessionId: String): ChatSessionDto {
    check(sessionId == id); calls += "get"; getGate?.await()
    getError?.let { throw ChatRequestException(it, "error") }
    return ChatSessionDto(id, count)
  }
  override suspend fun sendMessage(sessionId: String, message: String): ChatTurnDto {
    check(sessionId == id); calls += "send:$message"; sendGate?.await()
    sendError?.let { throw ChatRequestException(it, "error") }
    count++
    return ChatTurnDto(id, "request", "completed", "A$count", count, null, null)
  }
  override suspend fun deleteSession(sessionId: String) { check(sessionId == id); calls += "delete"; check(!deleteFails) }
}
