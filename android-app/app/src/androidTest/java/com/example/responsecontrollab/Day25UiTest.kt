package com.example.responsecontrollab

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.day25.Day25ViewModel
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class Day25UiTest {
  @get:Rule val rule = createAndroidComposeRule<MainActivity>()
  private val repo = Day25UiRepository()
  private lateinit var vm: Day25ViewModel
  @Before fun setup() {
    rule.activityRule.scenario.onActivity { activity ->
      activity.viewModelStore.clear()
      vm = ViewModelProvider(activity,Day25ViewModel.factory(repo,object: CurrentSessionStore {
        private var id: String? = null
        override suspend fun read() = id
        override suspend fun save(sessionId: String) { id = sessionId }
        override suspend fun clear() { id = null }
      }))[Day25ViewModel.KEY,Day25ViewModel::class.java]
    }
    rule.activityRule.scenario.recreate()
    rule.onNodeWithTag("days_catalog").performScrollToNode(hasTestTag("day_25"))
    rule.onNodeWithTag("day_25").performClick()
  }

  @Test fun answeredSourcesMemoryAndRecreationDoNotReplay() {
    send("Моя цель")
    rule.onNodeWithTag("day25_transcript").performScrollToNode(hasText("doc.md — Session restore"))
    rule.onNodeWithText("doc.md — Session restore").assertIsDisplayed()
    rule.onNodeWithTag("day25_memory_toggle").performClick()
    rule.onNodeWithText("Моя цель (U1)").assertIsDisplayed()
    rule.activityRule.scenario.recreate()
    rule.onNodeWithText("Моя цель (U1)").assertIsDisplayed()
    rule.runOnIdle { assertEquals(1,repo.sends) }
  }

  @Test fun abstentionShowsSkippedMemoryAndErrorAddsNoSuccessfulPair() {
    rule.runOnIdle { repo.abstain = true }
    send("Неизвестное")
    rule.onNodeWithTag("day25_transcript").performScrollToNode(hasTestTag("day25_abstention"))
    rule.onNodeWithTag("day25_abstention").assertIsDisplayed()
    rule.runOnIdle { repo.reject = true }
    send("Следующее")
    rule.onNodeWithTag("day25_error").assertIsDisplayed()
    rule.onNodeWithTag("day25_send").assertIsNotEnabled()
    rule.runOnIdle { assertEquals(1,vm.uiState.value.visibleTurns.size); assertNull(vm.uiState.value.snapshot?.memory?.goal) }
  }

  @Test fun unknownSendReconcilesSavedSourcesWithoutRetry() {
    rule.runOnIdle { repo.lost = true }
    send("Моя цель")
    rule.onNodeWithTag("day25_send").assertIsNotEnabled()
    rule.onNodeWithTag("day25_read").performClick()
    rule.onNodeWithTag("day25_transcript").performScrollToNode(hasText("doc.md — Session restore"))
    rule.onNodeWithText("doc.md — Session restore").assertIsDisplayed()
    rule.runOnIdle { assertEquals(1,repo.sends); assertEquals(1,repo.reads) }
  }

  @Test fun loadingPreventsConcurrentSendAndReset() {
    rule.runOnIdle { repo.gate = CompletableDeferred() }
    send("Моя цель")
    rule.onNodeWithTag("day25_loading").assertIsDisplayed()
    rule.onNodeWithTag("day25_send").assertIsNotEnabled()
    rule.onNodeWithTag("day25_reset").assertIsNotEnabled()
    rule.runOnIdle { repo.gate!!.complete(Unit) }
    rule.waitUntil { !vm.uiState.value.busy }
    rule.runOnIdle { assertEquals(1,repo.sends) }
  }

  private fun send(text: String) {
    rule.onNodeWithTag("day25_input").performTextReplacement(text)
    Espresso.closeSoftKeyboard()
    rule.onNodeWithTag("day25_send").performClick()
    rule.waitForIdle()
  }
}

private class Day25UiRepository: Day25Repository {
  val id = "00000000-0000-0000-0000-000000000025"
  var snapshot = Day25Snapshot(id,0,0,Day25Memory(),emptyList(),emptyList())
  var sends = 0; var reads = 0; var abstain = false; var reject = false; var lost = false
  var gate: CompletableDeferred<Unit>? = null
  override suspend fun create() = snapshot
  override suspend fun read(id: String): Day25Snapshot { reads++; return snapshot }
  override suspend fun delete(id: String) {}
  override suspend fun send(id: String, body: Day25Message): Day25Result {
    sends++; gate?.await()
    if(reject) return Day25Result(id,"request","validation_failed",false,error=Day25Error("invalid_combined_payload","failure"))
    val n = snapshot.revision + 1
    val grounded = if(abstain) Day25Grounded("insufficient_context","Недостаточно контекста",emptyList(),emptyList()) else
      Day25Grounded("answered","Продолжается та же session",listOf(Day25Source("doc.md","Session restore","chunk")),listOf(Day25Citation("chunk","quote")))
    val turn = Day25Turn(n,"turn-$n",body.message,grounded,if(abstain) "skipped_model_abstention" else "applied")
    snapshot = snapshot.copy(revision=n,history_turn_count=n,
      memory=if(abstain) snapshot.memory else Day25Memory(Day25MemoryItem("goal",body.message,n,0,body.message.length)),
      history=snapshot.history + listOf(Day25History((n-1)*2,"user",body.message),Day25History((n-1)*2+1,"assistant",grounded.answer)),
      turns=snapshot.turns + turn)
    if(lost) throw Day25RequestException("unknown")
    return Day25Result(id,turn.turn_id,"accepted",true,grounded,turn.memory_update_status,snapshot)
  }
}
