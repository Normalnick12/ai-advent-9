package com.example.responsecontrollab.ui.compression

import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.main.MainDispatcherRule
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CompressionLabViewModelTest {
  @get:Rule val dispatcher = MainDispatcherRule()

  @Test fun identityIsSavedBeforeSendAndBusyPreventsDuplicates() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle()
    vm.compare(true); assertEquals(listOf("read"),f.calls)
    f.saveGate=CompletableDeferred(); vm.updateDraft(" U\n "); vm.send(); vm.send(); runCurrent()
    assertEquals(listOf("read","create","save"), f.calls)
    f.saveGate!!.complete(Unit); advanceUntilIdle()
    assertEquals(1,f.calls.count { it=="send" })
    assertEquals(listOf(" U\n ","A"),vm.uiState.value.messages.map { it.text })
    assertEquals(1,vm.uiState.value.historyTurnCount)
  }
  @Test fun compareRetainsChatAndItsOwnQuestionAndNeverChangesDurableSummary() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("U"); vm.send(); advanceUntilIdle()
    vm.updateDraft("unsent"); vm.compare(true); advanceUntilIdle()
    val result=vm.uiState.value
    assertEquals("unsent",result.draft); assertEquals(2,result.messages.size)
    assertEquals(1,result.historyTurnCount); assertNull(result.summary)
    assertEquals("local",result.comparison!!.compareSummary!!.text)
    vm.updateQuestion("different"); assertEquals(CompressionScenario.QUESTION,vm.uiState.value.comparison!!.question)
    vm.send(); advanceUntilIdle(); assertTrue(vm.uiState.value.comparisonStale)
  }
  @Test fun processMeasurementsDedupeAndMissingUsageStaysUnknown() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("U"); vm.send(); advanceUntilIdle(); vm.compare(false); advanceUntilIdle()
    f.fixedCompareId="same"; vm.compare(false); advanceUntilIdle(); vm.compare(false); advanceUntilIdle()
    assertEquals(3,vm.uiState.value.observations.size)
    assertEquals(1,vm.uiState.value.totals()["Ответы чата"]!!.calls)
    assertEquals(2,vm.uiState.value.totals()["Подготовка сравнения"]!!.calls)
    assertEquals(2,vm.uiState.value.totals()["Сравнение COMPRESSED"]!!.unknownCost)
    val cold=f.vm(); cold.initialize(); advanceUntilIdle()
    assertTrue(cold.uiState.value.observations.isEmpty()); assertTrue(cold.uiState.value.messages.isEmpty())
    assertEquals(1,cold.uiState.value.historyTurnCount)
    assertNull(cold.uiState.value.lastNormal)
  }
  @Test fun failedSendKeepsPaidSummaryAndDraft() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle(); f.failOutcome=true
    vm.updateDraft("U"); vm.send(); advanceUntilIdle()
    assertEquals("U",vm.uiState.value.draft); assertEquals(0,vm.uiState.value.historyTurnCount)
    assertEquals("durable",vm.uiState.value.summary!!.text)
    assertEquals(1,vm.uiState.value.totals()["Обновление сводки"]!!.calls)
    assertTrue(vm.uiState.value.messages.isEmpty())
  }
  @Test fun unknownCompareRequiresReadOnlyRefreshAndUnknownSendRequiresRecovery() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle()
    vm.updateDraft("U"); vm.send(); advanceUntilIdle(); f.networkFails=true
    vm.compare(false); advanceUntilIdle(); assertTrue(vm.uiState.value.compareRefreshRequired)
    vm.compare(false); assertEquals(1,f.calls.count { it=="compare" })
    vm.retryRestore(); advanceUntilIdle(); assertFalse(vm.uiState.value.compareRefreshRequired)
    assertEquals(1,f.calls.count { it=="compare" })
    vm.updateDraft("next"); vm.send(); advanceUntilIdle(); assertTrue(vm.uiState.value.recoveryRequired)
    assertEquals(2,vm.uiState.value.observations.count { it.result==null })
  }
  @Test fun restoreSummaryAndResetAreReadOnlyAndIsolated() = runTest {
    val f=Fixture(); f.saved=ID; val vm=f.vm(); vm.initialize(); vm.initialize(); advanceUntilIdle()
    assertEquals(listOf("read","get"),f.calls)
    vm.loadSummary(); advanceUntilIdle(); vm.loadSummary(); advanceUntilIdle()
    assertEquals(1,f.calls.count { it=="summary" })
    f.deleteFails=true; vm.newConversation(); advanceUntilIdle(); assertEquals(ID,vm.uiState.value.sessionId)
    f.deleteFails=false; vm.newConversation(); advanceUntilIdle()
    assertEquals(listOf("delete","clear"),f.calls.takeLast(2)); assertNull(vm.uiState.value.sessionId)
    assertTrue(vm.uiState.value.observations.isEmpty()); assertFalse(f.calls.contains("create"))
  }
  @Test fun fixturesAndDeltaLabelsAreDeterministic() = runTest {
    val f=Fixture(); val vm=f.vm(); vm.initialize(); advanceUntilIdle()
    repeat(4) { vm.loadFixture(it); assertEquals(CompressionScenario.messages()[it],vm.uiState.value.draft) }
    assertEquals(listOf("read"),f.calls)
    assertTrue(CompressionScenario.messages().all { it.length<=20000 })
    assertEquals("Дополнительный расход: 20 токенов (+20.0%)",compressionDeltaText(CompressionContextDto(tokenDelta=-20,percentDelta=-20.0)))
    assertEquals("Без изменения",compressionDeltaText(CompressionContextDto(tokenDelta=0,percentDelta=0.0)))
    assertTrue(compressionDeltaText(CompressionContextDto(tokenDelta=20,percentDelta=20.0)).startsWith("Экономия"))
  }

  private class Fixture : CompressionLabRepository, CurrentSessionStore {
    val calls=mutableListOf<String>(); var saved:String?=null; var count=0; var serial=0
    var saveGate:CompletableDeferred<Unit>?=null; var failOutcome=false; var networkFails=false; var deleteFails=false
    var fixedCompareId:String?=null
    fun vm()=CompressionLabViewModel(this,this)
    override suspend fun read():String? { calls+="read"; return saved }
    override suspend fun save(sessionId:String) { calls+="save"; saveGate?.await(); saved=sessionId }
    override suspend fun clear() { calls+="clear"; saved=null }
    override suspend fun create():CompressionSessionDto { calls+="create"; return CompressionSessionDto(ID,0) }
    override suspend fun get(id:String):CompressionSessionDto { calls+="get"; return CompressionSessionDto(id,count) }
    override suspend fun summary(id:String):CompressionSummaryDto? { calls+="summary"; return null }
    override suspend fun delete(id:String) { calls+="delete"; check(!deleteFails); count=0 }
    private fun phase()=CompressionPhaseDto("completed",true,TokenLabUsageDto(inputTokens=100,outputTokens=20,cachedInputTokens=0),
      TokenCostDto(status="available",amountUsd="0.000027"))
    override suspend fun send(id:String,message:String):CompressionOperationDto {
      calls+="send"; check(!networkFails); if(!failOutcome)count++
      return CompressionOperationDto(id,count,"r","s${++serial}",status=if(failOutcome)"error" else "completed",
        committed=!failOutcome,reply=if(failOutcome)null else "A",responsePhase=if(failOutcome)CompressionPhaseDto() else phase(),
        summaryPhase=if(failOutcome)phase() else CompressionPhaseDto(),summarySource="durable",
        durableSummary=if(failOutcome)CompressionSummaryDto(id,"durable",1,COMPRESSION_VERSION) else null)
    }
    override suspend fun compare(id:String,question:String,scenarioId:String?):CompressionOperationDto {
      calls+="compare"; check(!networkFails)
      return CompressionOperationDto(id,count,"r",fixedCompareId ?: "c${++serial}",kind="compare",status="completed",
        question=question,summaryPhase=phase(),full=CompressionBranchDto("completed","full",phase=phase(),score=3),
        compressed=CompressionBranchDto("completed","compressed",phase=CompressionPhaseDto("completed",true),score=2),
        summarySource="compare_local",compareSummary=CompressionSummaryDto(id,"local",3,COMPRESSION_VERSION))
    }
  }
  companion object { const val ID="11111111-1111-4111-8111-111111111111" }
}
