package com.example.responsecontrollab.ui.token

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class TokenLabViewModelTest {
  @get:Rule val dispatcher = MainDispatcherRule()

  @Test fun saveBeforeSendAndNormalFailuresRetainDiagnostics() = runTest {
    val f = Fixture(); val vm = f.vm()
    vm.initialize(); advanceUntilIdle()
    assertEquals(listOf("read"), f.calls)
    f.saveGate = CompletableDeferred()
    vm.updateDraft(" U\n "); vm.send(); vm.send(); runCurrent()
    assertEquals(listOf("read", "create", "save"), f.calls)
    f.saveGate!!.complete(Unit); advanceUntilIdle()
    assertEquals(1, f.calls.count { it == "send" })
    assertEquals(listOf(" U\n ", "A"), vm.uiState.value.messages.map { it.text })
    f.failOutcome = true
    vm.updateDraft("next"); vm.send(); advanceUntilIdle()
    assertEquals("next", vm.uiState.value.draft)
    assertEquals(1, vm.uiState.value.historyTurnCount)
    assertEquals(12L, vm.uiState.value.lastAttempt!!.diagnostics!!.currentMessageTokens)
    assertNull(vm.uiState.value.lastAttempt!!.usage)
    assertEquals(2, vm.uiState.value.observations.size)
  }

  @Test fun prepareDoesNotExecuteAndPermissionCannotBeReused() = runTest {
    val f = Fixture(); val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.prepareOverflow(); vm.prepareOverflow(); advanceUntilIdle()
    assertEquals(listOf("read", "create", "save", "prepare"), f.calls)
    assertTrue(vm.uiState.value.observations.isEmpty())
    assertEquals("p", vm.uiState.value.preparation!!.preparationId)
    f.executeGate = CompletableDeferred()
    vm.executeOverflow(); vm.executeOverflow(); runCurrent()
    assertNull(vm.uiState.value.preparation)
    assertEquals(1, f.calls.count { it == "execute" })
    f.executeGate!!.complete(Unit); advanceUntilIdle()
    vm.executeOverflow(); advanceUntilIdle()
    assertEquals(1, f.calls.count { it == "execute" })
    assertEquals(0, vm.uiState.value.historyTurnCount)
    vm.updateDraft("after"); assertTrue(vm.uiState.value.canSend)
  }

  @Test fun unknownProbeRequiresReadOnlyRefreshWhileUnknownSendRequiresReset() = runTest {
    val f = Fixture(); val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.prepareOverflow(); advanceUntilIdle(); f.executeFails = true
    vm.executeOverflow(); advanceUntilIdle()
    assertTrue(vm.uiState.value.probeRefreshRequired)
    assertFalse(vm.uiState.value.canSend)
    vm.executeOverflow(); vm.retryRestore(); advanceUntilIdle()
    assertEquals(1, f.calls.count { it == "execute" })
    assertFalse(vm.uiState.value.probeRefreshRequired)
    f.sendFails = true; vm.updateDraft("normal"); vm.send(); advanceUntilIdle()
    assertTrue(vm.uiState.value.recoveryRequired)
    vm.send(); advanceUntilIdle(); assertEquals(1, f.calls.count { it == "send" })
    vm.newConversation(); advanceUntilIdle()
    assertEquals(listOf("delete", "clear"), f.calls.takeLast(2))
    assertNull(vm.uiState.value.sessionId)
    assertTrue(vm.uiState.value.observations.isEmpty())
  }

  @Test fun coldStartHasOnlyIdentityAndCountAndRuntimeRowsAreBounded() = runTest {
    val f = Fixture(); f.saved = ID; f.count = 3
    val vm = f.vm(); vm.initialize(); vm.initialize(); advanceUntilIdle()
    assertEquals(listOf("read", "get"), f.calls)
    assertEquals(3, vm.uiState.value.historyTurnCount)
    assertTrue(vm.uiState.value.messages.isEmpty())
    repeat(22) { vm.updateDraft("U"); vm.send(); advanceUntilIdle() }
    assertEquals(20, vm.uiState.value.observations.size)
    assertEquals(3, vm.uiState.value.observations.first().number)
    val cold = f.vm(); cold.initialize(); advanceUntilIdle()
    assertNull(cold.uiState.value.lastAttempt)
    assertTrue(cold.uiState.value.observations.isEmpty())
    assertEquals(25, cold.uiState.value.historyTurnCount)
  }

  @Test fun saveFailureRetriesIdentityAndFixtureIsVisibleWithoutSend() = runTest {
    val f = Fixture(); val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    f.saveFails = true; vm.updateDraft("U"); vm.send(); advanceUntilIdle()
    assertFalse(vm.uiState.value.recoveryRequired)
    assertEquals(0, f.calls.count { it == "send" })
    f.saveFails = false; vm.send(); advanceUntilIdle()
    assertEquals(1, f.calls.count { it == "create" })
    vm.loadLongText()
    assertTrue(vm.uiState.value.draft.length <= 20000)
    assertEquals(201, vm.uiState.value.draft.lines().size)
    assertEquals(1, f.calls.count { it == "send" })
  }

  private class Fixture : TokenLabRepository, CurrentSessionStore {
    val calls = mutableListOf<String>()
    var saved: String? = null
    var count = 0
    var number = 0
    var saveGate: CompletableDeferred<Unit>? = null
    var executeGate: CompletableDeferred<Unit>? = null
    var saveFails = false
    var executeFails = false
    var sendFails = false
    var failOutcome = false
    fun vm() = TokenLabViewModel(this, this)
    override suspend fun read(): String? { calls += "read"; return saved }
    override suspend fun save(sessionId: String) { calls += "save"; saveGate?.await(); check(!saveFails); saved = sessionId }
    override suspend fun clear() { calls += "clear"; saved = null }
    override suspend fun create(): ChatSessionDto { calls += "create"; return ChatSessionDto(ID, 0) }
    override suspend fun get(id: String): ChatSessionDto { calls += "get"; return ChatSessionDto(id, count) }
    override suspend fun delete(id: String) { calls += "delete"; count = 0 }
    private fun result(status: String, committed: Boolean = false) = TokenTurnDto(ID, count, "r", "a${number++}", status,
      reply = if (committed) "A" else null, committed = committed, generationAttempted = committed,
      error = if (status == "error") ChatErrorDto("context_limit_exceeded", "Ошибка") else null,
      diagnostics = TokenDiagnosticsDto(currentMessageTokens = 12, savedHistoryTokens = 31, preflightInputTokens = 40,
        contextWindow = 128000, reservedOutputTokens = 1200, countCalls = 3))
    override suspend fun send(id: String, message: String): TokenTurnDto {
      calls += "send"; if (sendFails) throw ChatRequestException("unknown", "unknown")
      if (failOutcome) return result("error")
      count++; return result("completed", true)
    }
    override suspend fun prepare(id: String): TokenTurnDto {
      calls += "prepare"
      return result("prepared").copy(preparation = OverflowPreparationDto("p", "gpt-4o-mini", "v1", 13975,
        "block", "header", "ending", 531149, 531228, 546130, "sha", "start", "end", 0.0, Double.MAX_VALUE))
    }
    override suspend fun execute(id: String, preparationId: String): TokenTurnDto {
      calls += "execute"; executeGate?.await()
      if (executeFails) throw ChatRequestException("unknown", "unknown")
      return result("error").copy(generationAttempted = true)
    }
  }
  companion object { const val ID = "11111111-1111-4111-8111-111111111111" }
}
