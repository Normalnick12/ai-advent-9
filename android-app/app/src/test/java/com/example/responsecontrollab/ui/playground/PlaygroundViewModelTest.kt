package com.example.responsecontrollab.ui.playground

import com.example.responsecontrollab.PlaygroundFixture
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class PlaygroundViewModelTest {
  @get:Rule val dispatcher=MainDispatcherRule()
  @Test fun loadDraftBusyAndNoAutomaticLifecycle()=runTest {
    val f=PlaygroundFixture(); val vm=PlaygroundViewModel(f); vm.load(); advanceUntilIdle()
    assertEquals(0,f.creates); assertEquals(0,f.sends)
    vm.draft("VALIDATION_FAILED, возвращайся"); f.gate=CompletableDeferred(); vm.send(); runCurrent()
    vm.send(); vm.event("PAUSE"); vm.newConversation(); vm.load()
    assertEquals(1,f.sends); assertEquals(0,f.events); assertEquals(0,f.conversations)
    assertEquals("VALIDATION_FAILED, возвращайся",vm.uiState.value.pending)
    f.gate!!.complete(Unit); advanceUntilIdle()
    assertEquals(0,vm.uiState.value.current!!.task_state!!.revision)
    assertEquals("",vm.uiState.value.draft); assertNull(vm.uiState.value.pending)
  }
  @Test fun reviewedSetupCancelAndPartialCompletionRetainChoices()=runTest {
    val f=PlaygroundFixture(empty=true); val vm=PlaygroundViewModel(f); vm.load(); advanceUntilIdle()
    vm.openSetup(); vm.setupDraft(PlaygroundConfiguration(profile_preset="mentor",
      policy=CodingPolicyValues("MVVM","Views","RxJava",false))); vm.back()
    assertEquals(0,f.creates)
    vm.openSetup(); vm.setupDraft(PlaygroundConfiguration(profile_preset="mentor",
      policy=CodingPolicyValues("MVVM","Views","RxJava",false))); vm.create()
    assertEquals(0,f.creates)
    f.partial=true; vm.review(); vm.create(); advanceUntilIdle()
    val setup=vm.uiState.value.current!!.setup!!
    assertEquals("MVVM",setup.configuration.policy.required_architecture)
    vm.completeSetup(); advanceUntilIdle()
    assertEquals(setup.task_id,vm.uiState.value.current!!.setup!!.task_id)
    assertTrue(vm.uiState.value.current!!.ready); assertEquals(1,f.creates); assertEquals(1,f.completes)
  }
  @Test fun recoveryRejectionPauseAndDoneHaveDifferentOutcomes()=runTest {
    val f=PlaygroundFixture(); f.node("PLANNING_APPROVAL")
    val vm=PlaygroundViewModel(f); vm.load(); advanceUntilIdle()
    vm.event("IMPLEMENTATION_READY",educational=true); advanceUntilIdle()
    assertEquals("rejected",vm.uiState.value.receipts[vm.uiState.value.latest]!!.outcome)
    vm.event("PLAN_APPROVED"); advanceUntilIdle()
    vm.event("PAUSE"); advanceUntilIdle(); assertTrue(vm.uiState.value.current!!.can_send)
    vm.event("VALIDATION_FAILED"); advanceUntilIdle(); assertEquals(3,f.events)
    vm.event("RESUME"); advanceUntilIdle(); vm.event("IMPLEMENTATION_READY"); advanceUntilIdle()
    val memory=f.value.memory
    vm.event("VALIDATION_FAILED"); advanceUntilIdle()
    val r=vm.uiState.value.receipts[vm.uiState.value.latest]!!
    assertEquals("recovery_applied",r.outcome); assertEquals(memory,f.value.memory)
    assertFalse(vm.uiState.value.reconciliation); assertNull(vm.uiState.value.error)
    vm.event("IMPLEMENTATION_READY"); advanceUntilIdle(); vm.event("VALIDATION_CONFIRMED"); advanceUntilIdle()
    assertFalse(f.value.can_send); vm.draft("Hello"); vm.send(); assertEquals(0,f.sends)
    vm.inspect(r.attempt_id); assertEquals("EXECUTION_IMPLEMENT",vm.uiState.value.selectedReceipt!!.after!!.state_id)
  }
  @Test fun unknownTransportReadsOnceAndNeverReplays()=runTest {
    val f=PlaygroundFixture(); val vm=PlaygroundViewModel(f); vm.load(); advanceUntilIdle()
    f.lose=true; vm.draft("query"); vm.send(); advanceUntilIdle()
    assertEquals(1,f.sends); assertEquals(2,f.reads); assertEquals(2,f.value.memory!!.short_term.size)
    assertTrue(vm.uiState.value.receipts.isEmpty()); assertEquals("",vm.uiState.value.draft)
    vm.draft("another query")
    f.failRead=true; vm.refresh(); advanceUntilIdle(); vm.send(); vm.event("PAUSE")
    assertTrue(vm.uiState.value.reconciliation); assertEquals(1,f.sends); assertEquals(0,f.events)
  }
  @Test fun historicalReceiptsAreBoundedAndProcessRestoreCannotInventThem()=runTest {
    val f=PlaygroundFixture(); val vm=PlaygroundViewModel(f); vm.load(); advanceUntilIdle()
    vm.draft("first"); vm.send(); advanceUntilIdle()
    val first=vm.uiState.value.latest!!
    val original=vm.uiState.value.receipts[first]
    vm.selectProfile("mentor"); advanceUntilIdle()
    vm.inspect(first); assertEquals(original,vm.uiState.value.selectedReceipt)
    repeat(50) { vm.draft("q$it"); vm.send(); advanceUntilIdle() }
    assertEquals(50,vm.uiState.value.receipts.size); assertNull(vm.uiState.value.selectedReceipt)
    val cold=PlaygroundViewModel(f); cold.load(); advanceUntilIdle()
    assertTrue(cold.uiState.value.receipts.isEmpty()); assertEquals(102,cold.uiState.value.current!!.memory!!.short_term.size)
    cold.inspectPair(f.value.memory!!.session_id,0); assertNull(cold.uiState.value.selectedReceipt)
  }
  @Test fun evidenceStatusesAndCommitAreNotInferredFromAcceptance()=runTest {
    val f=PlaygroundFixture(); f.technical=true
    val r=f.send(f.value.reference!!.send("q")).receipt.copy(turn=InvariantTurn("error","accepted",commit_status="unknown"))
    assertTrue(summary(r).conversation.startsWith("Unknown")); assertTrue(summary(r).coverage.contains("Семантика"))
    assertEquals(6,listOf("not_applicable","not_attempted","not_required","unavailable","failed","unknown").map(::evidenceLabel).toSet().size)
    assertEquals(3,listOf("forward_applied","recovery_applied","rejected").map(::outcomeLabel).toSet().size)
  }
}
