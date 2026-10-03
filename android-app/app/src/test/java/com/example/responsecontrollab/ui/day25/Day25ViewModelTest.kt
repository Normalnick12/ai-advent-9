package com.example.responsecontrollab.ui.day25

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class Day25ViewModelTest {
  @get:Rule val dispatcher = MainDispatcherRule()

  @Test fun openingEmptyDoesNotCreateAndSendPersistsIdentityBeforeDispatch() = runTest {
    val f = Fixture(); val vm = f.vm()
    vm.initialize(); advanceUntilIdle()
    assertEquals(listOf("local-read"), f.calls)
    vm.updateDraft(" U1 "); vm.send(); advanceUntilIdle()
    assertEquals(listOf("local-read", "create", "save", "send:0: U1 "), f.calls)
    assertEquals(" U1 ", vm.uiState.value.visibleTurns.single().user)
    assertEquals(1, vm.uiState.value.snapshot?.revision)
    assertEquals("", vm.uiState.value.draft)
  }

  @Test fun coldStartReadsSameSessionBeforeSendAndDoesNotDisplayOldBubbles() = runTest {
    val f = Fixture(); f.saved = ID; f.accept("old"); f.readGate = CompletableDeferred()
    val vm = f.vm(); vm.updateDraft("next"); vm.initialize(); runCurrent()
    assertFalse(vm.uiState.value.canSend); vm.send(); assertEquals(0, f.sends)
    f.readGate!!.complete(Unit); advanceUntilIdle()
    assertEquals(1, vm.uiState.value.snapshot?.history_turn_count)
    assertEquals(f.snapshot.memory, vm.uiState.value.snapshot?.memory)
    assertTrue(vm.uiState.value.visibleTurns.isEmpty())
    vm.send(); advanceUntilIdle()
    assertEquals(listOf("next"), vm.uiState.value.visibleTurns.map { it.user })
    assertFalse(f.calls.contains("create"))
  }

  @Test fun lostSendIsReadWithoutReplayAndSavedSourcesAppear() = runTest {
    val f = Fixture(); f.loseAfterCommit = true
    val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("question"); vm.send(); advanceUntilIdle()
    assertTrue(vm.uiState.value.recoveryRequired)
    assertTrue(vm.uiState.value.visibleTurns.isEmpty())
    vm.send(); assertEquals(1, f.sends)
    vm.read(); advanceUntilIdle()
    assertFalse(vm.uiState.value.recoveryRequired)
    assertEquals("doc.md", vm.uiState.value.visibleTurns.single().grounded.sources.single().source)
    assertEquals("", vm.uiState.value.draft)
    assertEquals(1, f.sends)
  }

  @Test fun invalidTurnAddsNoPairOrMemoryAndRequiresExplicitRead() = runTest {
    val f = Fixture(); f.reject = true
    val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("question"); vm.send(); advanceUntilIdle()
    assertEquals(0, vm.uiState.value.snapshot?.revision)
    assertNull(vm.uiState.value.snapshot?.memory?.goal)
    assertTrue(vm.uiState.value.visibleTurns.isEmpty())
    assertEquals("question", vm.uiState.value.draft)
    assertFalse(vm.uiState.value.canSend)
    vm.read(); advanceUntilIdle(); assertTrue(vm.uiState.value.canSend)
    assertEquals(1, f.sends)
  }

  @Test fun abstentionIsConfirmedWithUnchangedMemoryAndNoSources() = runTest {
    val f = Fixture(); f.abstain = true
    val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("question"); vm.send(); advanceUntilIdle()
    assertEquals(1, vm.uiState.value.snapshot?.revision)
    assertNull(vm.uiState.value.snapshot?.memory?.goal)
    assertTrue(vm.uiState.value.visibleTurns.single().grounded.sources.isEmpty())
    assertEquals("skipped_model_abstention", vm.uiState.value.visibleTurns.single().memory_update_status)
    assertNull(vm.uiState.value.error)
  }

  @Test fun saveFailureKeepsSameCreatedIdentityAndDoesNotSend() = runTest {
    val f = Fixture(); f.saveFails = true
    val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("question"); vm.send(); advanceUntilIdle()
    assertEquals(0, f.sends); assertNull(f.saved)
    assertEquals(ID, vm.uiState.value.sessionId)
    f.saveFails = false; vm.send(); advanceUntilIdle()
    assertEquals(1, f.calls.count { it == "create" }); assertEquals(1, f.sends)
  }

  @Test fun resetRequiresDeleteAcknowledgementAndCanRepeatAfterLostResponse() = runTest {
    val f = Fixture(); f.saved = ID; f.deleteFails = true
    val vm = f.vm(); vm.initialize(); advanceUntilIdle(); vm.reset(); advanceUntilIdle()
    assertEquals(ID, f.saved); assertEquals(ID, vm.uiState.value.sessionId)
    assertTrue(vm.uiState.value.recoveryRequired)
    f.deleteFails = false; vm.reset(); advanceUntilIdle()
    assertNull(f.saved); assertNull(vm.uiState.value.sessionId)
    assertEquals(2, f.calls.count { it == "delete" })
    assertFalse(f.calls.contains("create"))
  }

  @Test fun malformedIdentityClearsLocallyAndMissingIdentityRemainsUntilExplicitReset() = runTest {
    for (id in listOf("bad-id", ID)) {
      val f = Fixture(); f.saved = id; f.readFails = true
      val vm = f.vm(); vm.initialize(); advanceUntilIdle()
      assertTrue(vm.uiState.value.recoveryRequired); assertEquals(id, f.saved)
      vm.reset(); advanceUntilIdle()
      assertNull(f.saved)
      assertEquals(if (id == ID) 1 else 0, f.calls.count { it == "delete" })
    }
  }

  @Test fun failedLocalReadCannotEraseAnUnknownIdentity() = runTest {
    val f = Fixture(); f.localReadFails = true; f.saved = ID
    val vm = f.vm(); vm.initialize(); advanceUntilIdle()
    assertFalse(vm.uiState.value.canReset); vm.reset(); vm.send(); advanceUntilIdle()
    assertEquals(listOf("local-read"), f.calls)
    f.localReadFails = false; vm.read(); advanceUntilIdle()
    assertEquals(ID, vm.uiState.value.sessionId); assertFalse(vm.uiState.value.recoveryRequired)
  }
}

private const val ID = "00000000-0000-0000-0000-000000000025"
private class Fixture: Day25Repository, CurrentSessionStore {
  val calls = mutableListOf<String>(); var saved: String? = null
  var sends = 0; var saveFails = false; var deleteFails = false; var readFails = false
  var localReadFails = false; var loseAfterCommit = false; var reject = false; var abstain = false
  var readGate: CompletableDeferred<Unit>? = null
  var snapshot = Day25Snapshot(ID, 0, 0, Day25Memory(), emptyList(), emptyList())
  fun vm() = Day25ViewModel(this, this)
  fun accept(message: String): Day25Turn {
    val number = snapshot.revision + 1
    val grounded = if (abstain) Day25Grounded("insufficient_context", "Недостаточно контекста", emptyList(), emptyList())
      else Day25Grounded("answered", "Answer $number", listOf(Day25Source("doc.md", "section", "chunk")), listOf(Day25Citation("chunk", "quote")))
    val turn = Day25Turn(number, "turn-$number", message, grounded, if(abstain) "skipped_model_abstention" else "applied")
    snapshot = snapshot.copy(revision = number, history_turn_count = number,
      memory = if(abstain) snapshot.memory else Day25Memory(Day25MemoryItem("goal", message, number, 0, message.length)),
      history = snapshot.history + listOf(Day25History((number-1)*2,"user",message), Day25History((number-1)*2+1,"assistant",grounded.answer)),
      turns = snapshot.turns + turn)
    return turn
  }
  override suspend fun create(): Day25Snapshot { calls += "create"; return snapshot }
  override suspend fun read(id: String): Day25Snapshot {
    calls += "get"; readGate?.await(); if(readFails) throw Day25RequestException("session_not_found"); return snapshot
  }
  override suspend fun send(id: String, body: Day25Message): Day25Result {
    sends++; calls += "send:${body.expected_revision}:${body.message}"
    if(reject) return Day25Result(ID,"request","validation_failed",false,error=Day25Error("invalid_combined_payload","error"))
    val turn = accept(body.message)
    if(loseAfterCommit) throw Day25RequestException("unknown")
    return Day25Result(ID,turn.turn_id,"accepted",true,turn.grounded,turn.memory_update_status,snapshot)
  }
  override suspend fun delete(id: String) { calls += "delete"; if(deleteFails) throw Day25RequestException("unknown") }
  override suspend fun read(): String? { calls += "local-read"; if(localReadFails) error("read failed"); return saved }
  override suspend fun save(sessionId: String) { calls += "save"; if(saveFails) error("save failed"); saved = sessionId }
  override suspend fun clear() { calls += "clear"; saved = null }
}
