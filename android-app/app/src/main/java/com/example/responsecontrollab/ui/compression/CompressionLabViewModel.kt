package com.example.responsecontrollab.ui.compression

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.chat.ChatMessage
import java.math.BigDecimal
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

object CompressionScenario {
  const val ID = "three-facts-v1"
  const val QUESTION = "Верни три строки: identifier=<идентификатор проекта>, limit=<лимит>, responsible=<ответственный>. Если значение неизвестно, напиши unknown. Без дополнительных пояснений"
  private const val ACK = "Ответь только: Принято. Не повторяй факты из диалога."
  fun messages(): List<String> {
    val filler = (100..179).joinToString("\n") { "Запись $it: учебный текст о повторной передаче истории и стоимости контекста." }
    return listOf("Учебный сценарий. identifier=ORBIT-7319\n$filler\n$ACK",
      "Учебный сценарий. limit=37\n$filler\n$ACK", "Учебный сценарий. responsible=Мира\n$ACK",
      "Подтверди готовность к проверке. $ACK")
  }
}
enum class CompressionActivity { IDLE, RESTORING, SENDING, COMPARING, RESETTING, READING_SUMMARY }
data class CompressionObservation(val id: String, val result: CompressionOperationDto? = null)
data class PhaseTotal(val calls: Int = 0, val input: Long = 0, val output: Long = 0,
  val cost: BigDecimal = BigDecimal.ZERO, val unknownCost: Int = 0, val unknownUsage: Int = 0)
data class CompressionLabState(
  val sessionId: String? = null, val identityKnown: Boolean = false,
  val initialized: Boolean = false, val restored: Boolean = false,
  val restoreFailed: Boolean = false, val recoveryRequired: Boolean = false,
  val compareRefreshRequired: Boolean = false, val historyTurnCount: Int? = null,
  val draft: String = "", val question: String = CompressionScenario.QUESTION,
  val messages: List<ChatMessage> = emptyList(),
  val operation: CompressionActivity = CompressionActivity.IDLE,
  val error: String? = null, val lastNormal: CompressionOperationDto? = null,
  val comparison: CompressionOperationDto? = null,
  val summary: CompressionSummaryDto? = null, val summaryLoaded: Boolean = false,
  val summaryMetadata: CompressionSummaryMetadataDto? = null,
  val observations: List<CompressionObservation> = emptyList(), val generation: Int = 0,
) {
  val busy get() = operation != CompressionActivity.IDLE
  val ready get() = initialized && !restoreFailed && !recoveryRequired && !compareRefreshRequired && !busy
  val canSend get() = ready && draft.isNotBlank() && draft.length <= 20000
  val canCompare get() = ready && sessionId != null && question.isNotBlank() && question.length <= 20000
  val canReset get() = identityKnown && !busy
  val comparisonStale get() = comparison?.let { it.historyTurnCount != historyTurnCount } ?: false
  fun totals(): Map<String, PhaseTotal> {
    val totals = linkedMapOf<String, PhaseTotal>()
    fun add(key: String, phase: CompressionPhaseDto?) {
      if (phase?.generationAttempted != true) return
      val old = totals[key] ?: PhaseTotal()
      val cost = if (phase.cost.status == "available") phase.cost.amountUsd?.toBigDecimalOrNull() else null
      totals[key] = PhaseTotal(old.calls+1, old.input+(phase.usage?.inputTokens ?: 0),
        old.output+(phase.usage?.outputTokens ?: 0), old.cost+(cost ?: BigDecimal.ZERO),
        old.unknownCost+if (cost == null) 1 else 0,
        old.unknownUsage+if (phase.usage?.inputTokens == null || phase.usage.outputTokens == null) 1 else 0)
    }
    observations.mapNotNull { it.result }.forEach {
      if (it.kind == "send") { add("Обновление сводки", it.summaryPhase); add("Ответы чата", it.responsePhase) }
      else { add("Подготовка сравнения", it.summaryPhase); add("Сравнение FULL", it.full?.phase); add("Сравнение COMPRESSED", it.compressed?.phase) }
    }
    return totals
  }
}

class CompressionLabViewModel(private val repository: CompressionLabRepository,
  private val store: CurrentSessionStore) : ViewModel() {
  private val state = MutableStateFlow(CompressionLabState())
  val uiState = state.asStateFlow()
  private var identityPersisted = false
  private var invalidId = false

  fun initialize() { if (!state.value.initialized && !state.value.busy && !state.value.restoreFailed) restore() }
  fun retryRestore() { if (!state.value.busy && !state.value.recoveryRequired) restore() }
  private fun restore() {
    state.value = state.value.copy(operation = CompressionActivity.RESTORING, error = null)
    viewModelScope.launch {
      try {
        if (!state.value.identityKnown) {
          val id = store.read()
          invalidId = id != null && !runCatching { UUID.fromString(id).toString() == id.lowercase() }.getOrDefault(false)
          state.value = state.value.copy(sessionId = id, identityKnown = true)
          identityPersisted = true
        }
        check(!invalidId)
        val id = state.value.sessionId
        val metadata = id?.let { repository.get(it) }
        state.value = state.value.copy(initialized = true, restored = id != null, restoreFailed = false,
          compareRefreshRequired = false, historyTurnCount = metadata?.historyTurnCount ?: 0,
          summaryMetadata = metadata?.summaryMetadata)
      } catch (e: CancellationException) { throw e
      } catch (e: Exception) {
        val code = (e as? ChatRequestException)?.code
        val lost = invalidId || code in setOf("session_not_found", "summary_state_invalid", "summary_config_mismatch")
        state.value = state.value.copy(restoreFailed = true, recoveryRequired = lost,
          error = if (lost) "Диалог или сводка недоступны. Начните новый диалог." else "Не удалось восстановить диалог. Повторите проверку.")
      } finally { state.value = state.value.copy(operation = CompressionActivity.IDLE) }
    }
  }
  fun updateDraft(value: String) { if (!state.value.busy) state.value = state.value.copy(draft = value) }
  fun updateQuestion(value: String) { if (!state.value.busy) state.value = state.value.copy(question = value) }
  fun loadFixture(index: Int) { if (state.value.ready) CompressionScenario.messages().getOrNull(index)?.let(::updateDraft) }
  fun loadQuestion() = updateQuestion(CompressionScenario.QUESTION)
  fun send() { if (state.value.canSend) perform(false, false) }
  fun compare(scored: Boolean) { if (state.value.canCompare) perform(true, scored) }

  private suspend fun ensureIdentity(): String {
    val id = state.value.sessionId ?: repository.create().sessionId.also {
      identityPersisted = false; state.value = state.value.copy(sessionId = it, identityKnown = true)
    }
    if (!identityPersisted) { store.save(id); identityPersisted = true }
    return id
  }
  private fun perform(compare: Boolean, scored: Boolean) {
    val before = state.value
    state.value = before.copy(operation = if (compare) CompressionActivity.COMPARING else CompressionActivity.SENDING, error = null)
    viewModelScope.launch {
      var networkStarted = false
      try {
        val id = if (compare) requireNotNull(before.sessionId) else ensureIdentity()
        networkStarted = true
        val result = if (compare) repository.compare(id, before.question, if (scored) CompressionScenario.ID else null)
          else repository.send(id, before.draft)
        check(result.sessionId == id && result.historyTurnCount == requireNotNull(before.historyTurnCount) + if (result.committed) 1 else 0)
        if (result.committed) {
          check(!compare && !result.reply.isNullOrBlank())
          state.value = state.value.copy(draft = "", messages = before.messages +
            listOf(ChatMessage(true, before.draft), ChatMessage(false, result.reply)), historyTurnCount = result.historyTurnCount)
        }
        val old = state.value
        state.value = old.copy(lastNormal = if (compare) old.lastNormal else result,
          comparison = if (compare) result else old.comparison, error = result.errorMessage,
          observations = if (old.observations.any { it.id == result.attemptId }) old.observations
            else old.observations + CompressionObservation(result.attemptId, result))
        if (result.summarySource != "not_loaded") state.value = state.value.copy(summary = result.durableSummary,
          summaryLoaded = true, summaryMetadata = result.durableSummary?.let {
            CompressionSummaryMetadataDto(it.boundary, it.boundary+1, it.text.length, it.configVersion) })
      } catch (e: CancellationException) { throw e
      } catch (e: Exception) {
        val code = (e as? ChatRequestException)?.code
        val lost = code in setOf("session_not_found", "summary_state_invalid", "summary_config_mismatch")
        val uncertain = networkStarted && code !in setOf("session_busy", "validation_error", "session_not_found", "summary_state_invalid", "summary_config_mismatch")
        state.value = state.value.copy(recoveryRequired = lost || (uncertain && !compare),
          compareRefreshRequired = uncertain && compare,
          observations = if (uncertain) state.value.observations + CompressionObservation(UUID.randomUUID().toString()) else state.value.observations,
          error = when {
            !identityPersisted -> "Не удалось сохранить ID. Generation не выполнялась; повторите отправку."
            lost -> "Диалог или сводка недоступны. Начните новый диалог."
            uncertain && compare -> "Результат и расход сравнения неизвестны. Проверьте диалог; сравнение автоматически не повторяется."
            uncertain -> "Результат отправки неизвестен. Начните новый диалог."
            else -> (e as? ChatRequestException)?.message ?: "Не удалось завершить действие."
          })
      } finally { state.value = state.value.copy(operation = CompressionActivity.IDLE) }
    }
  }
  fun loadSummary() {
    val before = state.value
    if (before.busy || before.summaryLoaded || before.sessionId == null) return
    state.value = before.copy(operation = CompressionActivity.READING_SUMMARY, error = null)
    viewModelScope.launch {
      try { state.value = state.value.copy(summary = repository.summary(before.sessionId), summaryLoaded = true)
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) { state.value = state.value.copy(error = "Не удалось прочитать сохранённую сводку. Повторите раскрытие.")
      } finally { state.value = state.value.copy(operation = CompressionActivity.IDLE) }
    }
  }
  fun newConversation() {
    val before = state.value
    if (!before.canReset) return
    state.value = before.copy(operation = CompressionActivity.RESETTING, error = null)
    viewModelScope.launch {
      try {
        if (!invalidId) before.sessionId?.let { repository.delete(it) }
        store.clear(); identityPersisted = true; invalidId = false
        state.value = CompressionLabState(identityKnown = true, initialized = true, historyTurnCount = 0, generation = before.generation+1)
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) { state.value = before.copy(recoveryRequired = true, error = "Сброс не подтверждён. Повторите «Новый диалог».")
      } finally { state.value = state.value.copy(operation = CompressionActivity.IDLE) }
    }
  }
  companion object {
    const val KEY = "day_09_compression_lab"
    const val PREFERENCES = "day_09_current_session_" + COMPRESSION_VERSION
    fun factory(repository: CompressionLabRepository, store: CurrentSessionStore): ViewModelProvider.Factory =
      object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = CompressionLabViewModel(repository, store) as T
      }
  }
}
