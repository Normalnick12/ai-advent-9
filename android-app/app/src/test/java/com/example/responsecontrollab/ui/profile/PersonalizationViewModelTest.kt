package com.example.responsecontrollab.ui.profile

import com.example.responsecontrollab.ProfileFixture
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class PersonalizationViewModelTest {
  @get:Rule val dispatcher=MainDispatcherRule()
  @Test fun customCreateEditSelectAndColdReadNeverReplay()=runTest {
    val repo=ProfileFixture(); val vm=PersonalizationViewModel(repo)
    vm.load(); advanceUntilIdle(); vm.load(); advanceUntilIdle(); assertEquals(1,repo.reads)
    vm.edit(); vm.draft(ProfileDraft(name="Custom",skipBasics=true,explainTerms=true)); vm.save(); advanceUntilIdle()
    assertNull(vm.uiState.value.current!!.active()); assertEquals(1,repo.saves)
    val p=repo.value.profiles.single(); assertTrue(p.constraints.skip_basic_explanations && p.constraints.explain_unfamiliar_terms)
    vm.select(p); advanceUntilIdle(); assertEquals(p,vm.uiState.value.current!!.active())
    val memory=repo.value.memory
    vm.edit(p); vm.draft(vm.uiState.value.draft.copy(name="Renamed")); vm.save(); advanceUntilIdle()
    assertEquals(memory,repo.value.memory); assertEquals(1,repo.value.active()!!.revision)
    val cold=PersonalizationViewModel(repo); cold.load(); advanceUntilIdle()
    assertEquals(repo.value,cold.uiState.value.current); assertNull(cold.uiState.value.latest)
    assertEquals(0,repo.sends); assertEquals(1,repo.selects)
  }
  @Test fun selectIsNotOptimisticAndBusyDraftSurvives()=runTest {
    val repo=ProfileFixture().apply { prepared() }; val vm=PersonalizationViewModel(repo)
    vm.load(); advanceUntilIdle(); val a=repo.value.active(); val b=repo.value.profiles[1]
    repo.gate=CompletableDeferred(); vm.select(b); runCurrent()
    assertEquals(a,vm.uiState.value.current!!.active()); vm.select(b); vm.send()
    assertEquals(1,repo.selects); assertEquals(0,repo.sends)
    repo.gate!!.complete(Unit); advanceUntilIdle(); assertEquals(b,vm.uiState.value.current!!.active())
  }
  @Test fun unknownOutcomeReconcilesWithoutRepeatingMutationOrLosingDraft()=runTest {
    val repo=ProfileFixture(); val vm=PersonalizationViewModel(repo); vm.load(); advanceUntilIdle()
    vm.edit(); vm.draft(ProfileDraft(name="Uncertain")); repo.lose=true; vm.save(); advanceUntilIdle()
    assertEquals(1,repo.saves); assertEquals(2,repo.reads); assertEquals("Uncertain",vm.uiState.value.draft.name)
    assertEquals(1,vm.uiState.value.current!!.profiles.size); assertNotNull(vm.uiState.value.error)
    assertFalse(vm.uiState.value.recovery)
  }
  @Test fun probesRequireExplicitSelectionAndOutputsStaySeparate()=runTest {
    val repo=ProfileFixture().apply { prepared(); failedOutput=true }; val vm=PersonalizationViewModel(repo)
    vm.load(); advanceUntilIdle(); vm.probe("B"); advanceUntilIdle(); assertEquals(0,repo.probes)
    vm.probe("A"); advanceUntilIdle(); val o=vm.uiState.value.results.getValue("A")
    assertTrue(o.selection_checks.values.all { it.correct==true }); assertTrue(o.adherence_checks.values.all { it.status=="unavailable" })
    assertEquals(2,repo.value.memory!!.short_term.size)
    vm.inspect(o); vm.note(o.attempt_id,"Human note"); vm.page("main")
    vm.message("No style hints"); vm.send(); advanceUntilIdle()
    assertEquals(repo.value.active()!!.profile_id,repo.lastSend!!.profile_id)
    assertEquals("No style hints",repo.lastSend!!.message); assertEquals(1,repo.sends)
  }
  @Test fun failedReadRequiresRecoveryAndDoesNotInitialize()=runTest {
    val repo=ProfileFixture().apply { failRead=true }; val vm=PersonalizationViewModel(repo)
    vm.load(); advanceUntilIdle(); vm.initialize(); advanceUntilIdle()
    assertTrue(vm.uiState.value.recovery); assertEquals(0,repo.writes)
  }
}
