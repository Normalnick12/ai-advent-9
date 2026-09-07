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
class ChatViewModelTest {
  @get:Rule val dispatcher = MainDispatcherRule()

  @Test fun lazyCreationContextReuseAndReset() = runTest {
    val repo = FakeChatRepository()
    val vm = ChatViewModel(repo)
    assertTrue(repo.calls.isEmpty())
    vm.updateDraft(" U1 ")
    vm.send()
    vm.send()
    assertEquals(" U1 ", vm.uiState.value.pendingUser)
    advanceUntilIdle()
    assertEquals(listOf("create", "send:s1: U1 "), repo.calls)
    vm.updateDraft("U2")
    vm.send()
    advanceUntilIdle()
    assertEquals(4, vm.uiState.value.messages.size)
    assertEquals(2, vm.uiState.value.historyTurnCount)
    vm.newConversation()
    advanceUntilIdle()
    assertEquals("delete:s1", repo.calls.last())
    assertNull(vm.uiState.value.sessionId)
    assertEquals(0, vm.uiState.value.historyTurnCount)
    assertEquals("", vm.uiState.value.draft)
    vm.updateDraft("U3")
    vm.send()
    advanceUntilIdle()
    assertEquals(listOf("create", "send:s2:U3"), repo.calls.takeLast(2))
  }

  @Test fun createFailureAndLocalResetDoNotSend() = runTest {
    val repo = FakeChatRepository().apply { createError = true }
    val vm = ChatViewModel(repo)
    vm.updateDraft("Факт")
    vm.send()
    advanceUntilIdle()
    assertEquals(listOf("create"), repo.calls)
    assertEquals("Факт", vm.uiState.value.draft)
    assertFalse(vm.uiState.value.recoveryRequired)
    vm.newConversation()
    assertEquals(listOf("create"), repo.calls)
    assertEquals("", vm.uiState.value.draft)
  }

  @Test fun knownFailuresKeepTranscriptAndAllowExplicitRetry() = runTest {
    for (status in listOf("incomplete", "refused", "error", "session_busy", "validation_error")) {
      val repo = FakeChatRepository()
      val vm = ChatViewModel(repo)
      vm.updateDraft("Факт"); vm.send(); advanceUntilIdle()
      repo.outcome = status
      vm.updateDraft("Вопрос"); vm.send(); advanceUntilIdle()
      assertEquals(2, vm.uiState.value.messages.size)
      assertEquals(1, vm.uiState.value.historyTurnCount)
      assertEquals("Вопрос", vm.uiState.value.draft)
      assertTrue(vm.uiState.value.canSend)
      assertNull(vm.uiState.value.pendingUser)
    }
  }

  @Test fun lostAndUncertainSendNeedResetWithoutReplay() = runTest {
    for (status in listOf("session_not_found", "unknown")) {
      val repo = FakeChatRepository()
      val vm = ChatViewModel(repo)
      vm.updateDraft("Факт"); vm.send(); advanceUntilIdle()
      repo.outcome = status
      vm.updateDraft("Вопрос"); vm.send(); advanceUntilIdle()
      val calls = repo.calls.toList()
      assertTrue(vm.uiState.value.recoveryRequired)
      vm.send(); advanceUntilIdle()
      assertEquals(calls, repo.calls)
      assertEquals(2, vm.uiState.value.messages.size)
      assertEquals("Вопрос", vm.uiState.value.draft)
      vm.newConversation(); advanceUntilIdle()
      assertNull(vm.uiState.value.sessionId)
      assertEquals("delete:s1", repo.calls.last())
    }
  }

  @Test fun busyGuardsAndFailedDeleteRetainStateUntilConfirmed() = runTest {
    val repo = FakeChatRepository().apply { gate = CompletableDeferred() }
    val vm = ChatViewModel(repo)
    vm.updateDraft("Факт"); vm.send(); runCurrent()
    vm.newConversation(); vm.send(); vm.updateDraft("Замена")
    assertEquals(listOf("create", "send:s1:Факт"), repo.calls)
    assertEquals("Факт", vm.uiState.value.draft)
    repo.gate!!.complete(Unit); advanceUntilIdle()
    for (code in listOf("session_busy", "unknown")) {
      repo.deleteError = code
      vm.newConversation(); advanceUntilIdle()
      assertEquals("s1", vm.uiState.value.sessionId)
      assertEquals(2, vm.uiState.value.messages.size)
      assertTrue(vm.uiState.value.recoveryRequired)
    }
    repo.deleteError = null
    vm.newConversation(); advanceUntilIdle()
    assertTrue(vm.uiState.value.messages.isEmpty())
    assertNull(vm.uiState.value.sessionId)
  }
}

private class FakeChatRepository : ChatRepository {
  val calls = mutableListOf<String>()
  var createError = false
  var deleteError: String? = null
  var outcome = "completed"
  var gate: CompletableDeferred<Unit>? = null
  private var sessions = 0
  private var count = 0
  override suspend fun createSession(): ChatSessionDto {
    calls += "create"
    if (createError) throw ChatRequestException("unknown", "Нет сети")
    sessions++; count = 0
    return ChatSessionDto("s$sessions", 0)
  }
  override suspend fun sendMessage(sessionId: String, message: String): ChatTurnDto {
    calls += "send:$sessionId:$message"
    gate?.await()
    if (outcome !in setOf("completed", "incomplete", "refused", "error")) throw ChatRequestException(outcome, "Ошибка")
    if (outcome == "completed") count++
    return ChatTurnDto(sessionId, "r", outcome, if (outcome == "completed") "Ответ" else null, count, null,
      if (outcome == "completed") null else ChatErrorDto("llm_$outcome", "Ответ не завершён"))
  }
  override suspend fun deleteSession(sessionId: String) {
    calls += "delete:$sessionId"
    deleteError?.let { throw ChatRequestException(it, "Ошибка сброса") }
  }
}
