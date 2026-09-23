package com.example.responsecontrollab.ui.watch

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DependencyWatchViewModelTest {
  @get:Rule val dispatcher = MainDispatcherRule()
  private class MemoryStore : WatchReceiptStore {
    var saved = WatchReceipts()
    override fun load() = saved
    override fun save(value: WatchReceipts) { saved = value }
  }
  private fun facts(id: String) = WatchFactsDto(id, "androidx.core", "core-ktx", 3600, 3,
    "2026-09-23T10:00:00Z", "2026-09-23T11:00:00Z", "active", 0, 0)
  private fun operation(request: WatchRequestDto, ids: List<String> = listOf("watch1")) = WatchOperationDto(
    "op", request.prompt, request.operation, selected_watch_id = request.watch_id,
    calls = ids.map { WatchCallDto(id = it, outcome = "completed", receipt = facts(it)) },
    outcome = "completed", invocation = "observed")

  @Test fun duplicateSendOnePostAndNoInitialOrRestoreReplay() = runTest {
    val gate = CompletableDeferred<Unit>()
    val calls = mutableListOf<WatchRequestDto>()
    val store = MemoryStore()
    val repo = DependencyWatchRepository { calls += it; gate.await(); operation(it, listOf("one", "two")) }
    val vm = DependencyWatchViewModel(repo, store)
    advanceUntilIdle(); assertTrue(calls.isEmpty())
    vm.send(); vm.send(); runCurrent()
    assertEquals(1, calls.size)
    gate.complete(Unit); advanceUntilIdle()
    assertEquals(listOf("one", "two"), store.saved.watches.map { it.watch_id })
    vm.selectWatch("two")
    val restored = DependencyWatchViewModel(repo, store)
    advanceUntilIdle()
    assertEquals("two", restored.uiState.value.receipts.selectedId)
    assertNull(restored.uiState.value.result)
    assertEquals(1, calls.size)
    restored.selectOperation("summary"); restored.send(); advanceUntilIdle()
    assertEquals("two", calls.last().watch_id)
    assertEquals("summary", calls.last().operation)
  }

  @Test fun unknownNewCreateRetainsIdentityAndClearsPriorEvidence() = runTest {
    var fail = false
    var calls = 0
    val store = MemoryStore()
    val vm = DependencyWatchViewModel(DependencyWatchRepository {
      calls++; if (fail) error("connection lost") else operation(it)
    }, store)
    vm.send(); advanceUntilIdle()
    fail = true; vm.send(); assertNull(vm.uiState.value.result); advanceUntilIdle()
    assertNotNull(vm.uiState.value.error)
    assertEquals("watch1", vm.uiState.value.receipts.selectedId)
    assertEquals("watch1", store.saved.selectedId)
    advanceUntilIdle(); assertEquals(2, calls)
  }

  @Test fun summaryRequiresSelectionAndBlankDoesNotSend() = runTest {
    var calls = 0
    val vm = DependencyWatchViewModel(DependencyWatchRepository { calls++; operation(it) }, MemoryStore())
    vm.selectOperation("summary"); vm.send(); advanceUntilIdle()
    assertEquals(0, calls)
    vm.selectOperation("create"); vm.editPrompt(" "); vm.send(); advanceUntilIdle()
    assertEquals(0, calls)
  }

  @Test fun snapshotImmutableAndTypedSummaryIndependentOfDraft() = runTest {
    val gate = CompletableDeferred<Unit>()
    val vm = DependencyWatchViewModel(DependencyWatchRepository { gate.await(); operation(it) }, MemoryStore())
    vm.editPrompt("Submitted"); vm.send(); runCurrent(); vm.editPrompt("New draft")
    gate.complete(Unit); advanceUntilIdle()
    assertEquals("Submitted", vm.uiState.value.result?.submitted_prompt)
    assertEquals("New draft", vm.uiState.value.prompt)
  }
}
