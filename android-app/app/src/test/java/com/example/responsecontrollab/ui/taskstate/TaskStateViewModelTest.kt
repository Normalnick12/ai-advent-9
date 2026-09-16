package com.example.responsecontrollab.ui.taskstate

import com.example.responsecontrollab.TaskFixture
import com.example.responsecontrollab.data.TaskReadiness
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class TaskStateViewModelTest {
  @get:Rule val dispatcher=MainDispatcherRule()
  @Test fun pausedSendTwoConversationsAndExplicitResume()=runTest {
    val repo=TaskFixture(); val vm=TaskStateViewModel(repo); vm.load(); advanceUntilIdle()
    vm.message("Execution"); vm.send(); advanceUntilIdle(); assertEquals(2,repo.value.memory!!.short_term.size)
    vm.event("PAUSE"); advanceUntilIdle(); val paused=repo.value.task_state
    vm.lifecycle("new-conversation"); advanceUntilIdle(); assertTrue(repo.value.memory!!.short_term.isEmpty())
    vm.message("Где мы остановились?"); vm.send(); advanceUntilIdle()
    assertEquals(paused,repo.value.task_state); assertEquals(2,repo.value.memory!!.short_term.size)
    vm.event("IMPLEMENTATION_READY"); advanceUntilIdle(); assertEquals(1,repo.events)
    vm.lifecycle("new-conversation"); advanceUntilIdle(); assertTrue(repo.value.memory!!.short_term.isEmpty())
    vm.event("RESUME"); advanceUntilIdle(); vm.message("Продолжим"); vm.send(); advanceUntilIdle()
    assertEquals(3,repo.sends); assertEquals(2,repo.events); assertEquals(2,repo.lifecycles)
    assertEquals("EXECUTION_IMPLEMENT",repo.value.task_state!!.state_id)
    assertEquals(repo.value.task_state!!.revision,repo.lastSend!!.state_revision)
    vm.page("inspector"); vm.note("Observation"); vm.load(); advanceUntilIdle()
    assertEquals(1,repo.reads); assertEquals("Observation",vm.uiState.value.note)
  }
  @Test fun eventsAreNotOptimisticAndLostOutcomeReadsWithoutReplay()=runTest {
    val repo=TaskFixture(); val vm=TaskStateViewModel(repo); vm.load(); advanceUntilIdle()
    repo.gate=CompletableDeferred(); repo.lose=true
    vm.event("PAUSE"); runCurrent(); vm.event("PAUSE"); vm.lifecycle("new-task")
    assertEquals("ACTIVE",vm.uiState.value.current!!.task_state!!.status); assertEquals(1,repo.events)
    repo.gate!!.complete(Unit); advanceUntilIdle()
    assertEquals("PAUSED",vm.uiState.value.current!!.task_state!!.status); assertEquals(2,repo.reads)
    assertEquals(1,repo.events); assertEquals(0,repo.lifecycles); assertEquals("unavailable",vm.uiState.value.dispatch)
    val cold=TaskStateViewModel(repo); cold.load(); advanceUntilIdle(); assertNull(cold.uiState.value.latest)
    assertEquals(repo.value,cold.uiState.value.current)
  }
  @Test fun staleRejectionShowsNotDispatchedAndReadsWithoutReplay()=runTest {
    val repo=TaskFixture(); val vm=TaskStateViewModel(repo); vm.load(); advanceUntilIdle()
    val before=repo.value
    repo.eventFailure=retrofit2.HttpException(retrofit2.Response.error<Any>(409,
      okhttp3.ResponseBody.create(null,"{\"error\":\"stale_task_state\",\"dispatch\":\"not_dispatched\"}")))
    vm.event("PAUSE"); advanceUntilIdle()
    assertEquals(before,vm.uiState.value.current); assertEquals("not_dispatched",vm.uiState.value.dispatch)
    assertNull(vm.uiState.value.latest); assertEquals(1,repo.events); assertEquals(2,repo.reads)
  }
  @Test fun partialReadinessAndReadFailureBlockProgressButAllowExplicitRecovery()=runTest {
    val repo=TaskFixture(); repo.value=repo.value.copy(task_state=null,ready=false,readiness=TaskReadiness(true,true,false))
    val vm=TaskStateViewModel(repo); vm.load(); advanceUntilIdle(); vm.message("x"); vm.send(); vm.event("PAUSE"); advanceUntilIdle()
    assertEquals(0,repo.sends); assertEquals(0,repo.events); vm.initializeState(); advanceUntilIdle(); assertEquals(1,repo.writes)
    repo.failRead=true; vm.refresh(); advanceUntilIdle(); vm.initializeState(); advanceUntilIdle()
    assertTrue(vm.uiState.value.recovery); assertEquals(1,repo.writes)
  }
}
