package com.example.responsecontrollab.ui.invariants

import com.example.responsecontrollab.InvariantsFixture
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class InvariantsViewModelTest {
  @get:Rule val dispatcher=MainDispatcherRule()
  @Test fun duplicateClicksAndLoadNeverReplayHistoricalAttempt()=runTest {
    val f=InvariantsFixture(); val vm=InvariantsViewModel(f); vm.load(); advanceUntilIdle()
    f.gate=CompletableDeferred(); vm.propose("conflicting-stack"); runCurrent()
    vm.propose("compatible-retry"); vm.setup(); vm.lifecycle("new-task"); vm.load(); runCurrent()
    assertEquals(1,f.proposals); assertEquals(0,f.setups); assertEquals(0,f.lifecycles)
    f.gate!!.complete(Unit); advanceUntilIdle()
    val o=vm.uiState.value.latest!!; assertEquals("not_dispatched",o.provider_dispatch); assertEquals("committed",o.turn.commit_status)
    vm.lifecycle("new-conversation"); advanceUntilIdle(); vm.page("inspector"); vm.load(); advanceUntilIdle()
    assertEquals(o,vm.uiState.value.latest); assertNotEquals(o.memory.session_id,vm.uiState.value.current!!.memory!!.session_id)
    assertEquals(1,f.reads)
  }
  @Test fun lostResponseReadsDurablePairWithoutInventingReceipt()=runTest {
    val f=InvariantsFixture(); val vm=InvariantsViewModel(f); vm.load(); advanceUntilIdle()
    f.lose=true; vm.propose("conflicting-stack"); advanceUntilIdle()
    assertEquals(1,f.proposals); assertEquals(2,f.reads); assertEquals(2,vm.uiState.value.current!!.memory!!.short_term.size)
    assertNull(vm.uiState.value.latest); assertNotNull(vm.uiState.value.error)
    vm.refresh(); advanceUntilIdle(); assertEquals(1,f.proposals)
  }
  @Test fun partialSetupAndReadFailureRequireExplicitRecovery()=runTest {
    val f=InvariantsFixture(); f.value=f.value.copy(policy=null,ready=false,can_propose=false,readiness=f.value.readiness.copy(policy_ready=false))
    val id=f.value.memory!!.task_id; val vm=InvariantsViewModel(f); vm.load(); advanceUntilIdle()
    vm.propose("compatible-retry"); assertEquals(0,f.proposals)
    f.failSetup=true; vm.setup(); advanceUntilIdle(); assertEquals(1,f.setups); assertEquals(id,vm.uiState.value.current!!.memory!!.task_id)
    f.failSetup=false; vm.setup(); advanceUntilIdle(); assertTrue(vm.uiState.value.current!!.ready)
    f.failRead=true; vm.refresh(); advanceUntilIdle(); vm.propose("compatible-retry"); vm.setup(); advanceUntilIdle()
    assertTrue(vm.uiState.value.recovery); assertEquals(0,f.proposals); assertEquals(2,f.setups)
    f.failRead=false; vm.refresh(); advanceUntilIdle(); assertFalse(vm.uiState.value.recovery)
  }
  @Test fun stateGatingAndTechnicalReceiptUseBackendOutcomes()=runTest {
    val f=InvariantsFixture(); val vm=InvariantsViewModel(f); vm.load(); advanceUntilIdle()
    vm.event("PAUSE"); advanceUntilIdle(); vm.propose("compatible-retry"); assertEquals(0,f.proposals)
    vm.event("RESUME"); advanceUntilIdle(); f.technical=true; vm.propose("compatible-retry"); advanceUntilIdle()
    assertEquals("dispatched",vm.uiState.value.latest!!.provider_dispatch)
    assertEquals("not_attempted",vm.uiState.value.latest!!.turn.commit_status)
    assertTrue(vm.uiState.value.current!!.memory!!.short_term.isEmpty()); assertNotNull(vm.uiState.value.error)
  }
}
