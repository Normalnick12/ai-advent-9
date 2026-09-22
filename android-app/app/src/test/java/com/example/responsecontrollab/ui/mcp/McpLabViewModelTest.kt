package com.example.responsecontrollab.ui.mcp

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class McpLabViewModelTest {
  @get:Rule val dispatcher = MainDispatcherRule()

  private fun receipt(prompt: String, mode: String, outcome: String = "completed") = McpLabOperationDto(
    "op", prompt, mode, response_id = "resp", outcome = outcome, invocation = "observed")

  @Test fun noInitialSendAndNewProcessHasNoReceipt() = runTest {
    var calls = 0
    val repository = McpLabRepository { p, m -> calls++; receipt(p, m) }
    val vm = McpLabViewModel(repository)
    assertEquals(MCP_DEFAULT_PROMPT, vm.uiState.value.prompt)
    assertEquals("forced", vm.uiState.value.mode)
    advanceUntilIdle()
    assertEquals(0, calls)
    vm.send(); advanceUntilIdle()
    assertNotNull(vm.uiState.value.result)
    val recreated = McpLabViewModel(repository)
    advanceUntilIdle()
    assertNull(recreated.uiState.value.result)
    assertEquals(1, calls)
  }

  @Test fun duplicateTapIsBlockedAndDraftDoesNotChangeSubmittedSnapshot() = runTest {
    val gate = CompletableDeferred<Unit>()
    val calls = mutableListOf<Pair<String, String>>()
    val vm = McpLabViewModel(McpLabRepository { p, m -> calls += p to m; gate.await(); receipt(p, m) })
    vm.editPrompt("Original"); vm.send(); vm.send(); runCurrent()
    vm.editPrompt("Edited"); vm.selectMode("auto")
    assertTrue(vm.uiState.value.isLoading)
    assertNull(vm.uiState.value.result)
    assertEquals(listOf("Original" to "forced"), calls)
    gate.complete(Unit); advanceUntilIdle()
    assertEquals("Original", vm.uiState.value.submittedPrompt)
    assertEquals("forced", vm.uiState.value.submittedMode)
    assertEquals("Original", vm.uiState.value.result?.submitted_prompt)
    assertEquals("Edited", vm.uiState.value.prompt)
  }

  @Test fun failureAfterSuccessNeverShowsOldEvidence() = runTest {
    var fail = false
    val gate = CompletableDeferred<Unit>()
    val vm = McpLabViewModel(McpLabRepository { p, m ->
      if (fail) { gate.await(); error("Network") }; receipt(p, m)
    })
    vm.send(); advanceUntilIdle(); assertNotNull(vm.uiState.value.result)
    fail = true; vm.editPrompt("New"); vm.send(); runCurrent()
    assertNull(vm.uiState.value.result)
    gate.complete(Unit); advanceUntilIdle()
    assertNull(vm.uiState.value.result)
    assertNotNull(vm.uiState.value.error)
    assertEquals("New", vm.uiState.value.submittedPrompt)
  }

  @Test fun allBackendOutcomesStayExplicit() = runTest {
    for (outcome in listOf("completed", "not_called", "mcp_error", "tool_error", "incomplete", "provider_error")) {
      val vm = McpLabViewModel(McpLabRepository { p, m -> receipt(p, m, outcome) })
      vm.selectMode("auto"); vm.send(); advanceUntilIdle()
      assertEquals(outcome, vm.uiState.value.result?.outcome)
      assertEquals("auto", vm.uiState.value.result?.mode)
      assertFalse(vm.uiState.value.isLoading)
    }
  }

  @Test fun blankAttemptClearsOldSuccessWithoutCall() = runTest {
    var calls = 0
    val vm = McpLabViewModel(McpLabRepository { p, m -> calls++; receipt(p, m) })
    vm.send(); advanceUntilIdle(); vm.editPrompt(" "); vm.send()
    assertNull(vm.uiState.value.result)
    assertNotNull(vm.uiState.value.error)
    assertEquals(1, calls)
  }
}
