package com.example.responsecontrollab.ui.memory

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class MemoryLayersViewModelTest {
  @get:Rule val dispatcher=MainDispatcherRule()

  @Test fun readAndColdRestoreDoNotMutateOrGenerate() = runTest {
    val repo=MemoryFixture()
    val vm=MemoryLayersViewModel(repo)
    vm.load(); advanceUntilIdle()
    vm.load(); advanceUntilIdle()
    assertEquals(1,repo.reads); assertEquals(0,repo.mutations)
    assertNull(vm.uiState.value.latest)
    val cold=MemoryLayersViewModel(repo); cold.load(); advanceUntilIdle()
    assertEquals(repo.currentState, cold.uiState.value.current)
    assertTrue(cold.uiState.value.results.isEmpty()); assertEquals(0,repo.probes)
  }

  @Test fun explicitWriteUsesLayerAndSnapshotAndRemoveOmitsNull() = runTest {
    val repo=MemoryFixture(); val vm=MemoryLayersViewModel(repo)
    vm.load(); advanceUntilIdle()
    vm.write("WORKING","current_architecture","MVI"); advanceUntilIdle()
    assertEquals("WORKING",repo.lastMutation?.layer)
    assertEquals("a".repeat(64),repo.lastMutation?.snapshot_id)
    vm.removeArchitecture(); advanceUntilIdle()
    val json=Json.encodeToString(repo.lastMutation!!)
    assertFalse(json.contains("value")); assertTrue(json.contains("remove"))
    assertEquals(2,repo.mutations); assertEquals(0,repo.probes)
  }

  @Test fun lostLifecycleResponseReconcilesWithoutReplay() = runTest {
    val repo=MemoryFixture(); val vm=MemoryLayersViewModel(repo)
    vm.load(); advanceUntilIdle(); repo.lose=true
    vm.transition("new-task"); advanceUntilIdle()
    assertEquals(1,repo.transitions)
    assertEquals("b".repeat(64),vm.uiState.value.current?.state?.snapshot_id)
    assertNotNull(vm.uiState.value.error); assertFalse(vm.uiState.value.recovery)
    assertEquals(2,repo.reads)
  }

  @Test fun probeDoesNotReplaceInputSuccessWithOutputFailure() = runTest {
    val repo=MemoryFixture(); val vm=MemoryLayersViewModel(repo)
    vm.load(); advanceUntilIdle()
    vm.verify("A"); advanceUntilIdle()
    val obs=vm.uiState.value.results.getValue("A")
    assertEquals(true,obs.input_checks["effective_architecture"]?.correct)
    assertEquals(false,obs.output_checks["effective_architecture"]?.correct)
    assertEquals("a".repeat(64),vm.uiState.value.current?.state?.snapshot_id)
    vm.clearObservations()
    assertTrue(vm.uiState.value.results.isEmpty()); assertEquals(0,repo.mutations)
    assertEquals(1,repo.probes)
  }

  @Test fun busyRejectsSecondProbeAndMutation() = runTest {
    val repo=MemoryFixture(); val vm=MemoryLayersViewModel(repo)
    vm.load(); advanceUntilIdle(); repo.gate=CompletableDeferred()
    vm.verify("A"); runCurrent()
    vm.verify("A"); vm.transition("new-task")
    assertEquals(1,repo.probes); assertEquals(0,repo.transitions)
    repo.gate!!.complete(Unit); advanceUntilIdle()
    assertFalse(vm.uiState.value.busy)
  }

  @Test fun inapplicableProbeAndFailedReadDoNotInitialize() = runTest {
    val repo=MemoryFixture(); val vm=MemoryLayersViewModel(repo)
    vm.load(); advanceUntilIdle(); vm.verify("E"); advanceUntilIdle()
    assertEquals(0,repo.probes)
    repo.failRead=true; vm.refresh(); advanceUntilIdle(); vm.initialize(); advanceUntilIdle()
    assertTrue(vm.uiState.value.recovery); assertEquals(0,repo.mutations)
  }
}

class MemoryFixture : MemoryLayersRepository {
  var reads=0; var mutations=0; var transitions=0; var probes=0
  var lose=false; var failRead=false
  var gate: CompletableDeferred<Unit>?=null
  var lastMutation: MemoryMutationRequest?=null
  var currentState=MemoryCurrent(state=MemoryStateDto(
    "00000000-0000-0000-0000-000000000001","00000000-0000-0000-0000-000000000002",
    "00000000-0000-0000-0000-000000000003",0,"a".repeat(64),
    working=mapOf("task" to "Checkout","current_architecture" to "MVI","release_marker" to "RC-42"),
    long_term=mapOf("project_code" to "ORION-17","preferred_architecture" to "MVVM")),
    applicable_stages=listOf("A"))
  override suspend fun current(): MemoryCurrent { reads++; if(failRead) error("offline"); return currentState }
  override suspend fun catalog()=MemoryCatalog("error_title=Сбой-47","same query",emptyMap(),emptyMap())
  override suspend fun initialize(): MemoryCurrent { mutations++; return currentState }
  override suspend fun mutate(body: MemoryMutationRequest): MemoryCurrent { mutations++; lastMutation=body; return currentState }
  override suspend fun transition(action: String,body: MemorySnapshotRequest): MemoryCurrent {
    transitions++; currentState=currentState.copy(state=currentState.state!!.copy(snapshot_id="b".repeat(64)))
    if(lose) error("lost response")
    return currentState
  }
  override suspend fun send(body: MemorySendRequest): MemoryOperation = error("unexpected send")
  override suspend fun verify(stage: String,body: MemorySnapshotRequest): MemoryOperation {
    probes++; gate?.await()
    val obs=MemoryObservation("attempt",body.snapshot_id,currentState.state!!,MemorySelection(),
      buildJsonObject { put("input","actual input") },"completed",reply="MVVM",stage=stage,
      input_checks=mapOf("effective_architecture" to MemoryCheck("available",true,"MVI",values=listOf("MVI"))),
      output_checks=mapOf("effective_architecture" to MemoryCheck("mismatch",false,"MVI","MVVM")))
    return MemoryOperation(currentState,obs)
  }
}
