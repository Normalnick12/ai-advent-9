package com.example.responsecontrollab.ui.token

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.chat.ChatMessage
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class TokenOperation { IDLE, RESTORING, CREATING, SAVING_ID, SENDING, PREPARING, EXECUTING, RESETTING }
data class TokenObservation(val number: Int, val id: String, val outcome: String, val result: TokenTurnDto?)
data class TokenLabState(
  val sessionId: String? = null,
  val identityKnown: Boolean = false,
  val initialized: Boolean = false,
  val restored: Boolean = false,
  val restoreFailed: Boolean = false,
  val recoveryRequired: Boolean = false,
  val probeRefreshRequired: Boolean = false,
  val historyTurnCount: Int? = null,
  val draft: String = "",
  val messages: List<ChatMessage> = emptyList(),
  val operation: TokenOperation = TokenOperation.IDLE,
  val error: String? = null,
  val lastAttempt: TokenTurnDto? = null,
  val preparation: OverflowPreparationDto? = null,
  val observations: List<TokenObservation> = emptyList(),
  val nextNumber: Int = 1,
  val generation: Int = 0,
) {
  val busy get() = operation != TokenOperation.IDLE
  val ready get() = initialized && !restoreFailed && !recoveryRequired && !probeRefreshRequired && !busy
  val canSend get() = ready && draft.isNotBlank() && draft.length <= 20000
  val canReset get() = identityKnown && !busy
}

class TokenLabViewModel(private val repository: TokenLabRepository, private val store: CurrentSessionStore) : ViewModel() {
  private val state = MutableStateFlow(TokenLabState())
  val uiState = state.asStateFlow()
  private var identityPersisted = false
  private var invalidId = false

  fun initialize() {
    if (!state.value.initialized && !state.value.busy && !state.value.restoreFailed) restore()
  }
  fun retryRestore() {
    if (!state.value.busy && (state.value.restoreFailed || state.value.probeRefreshRequired)) restore()
  }
  private fun restore() {
    state.value = state.value.copy(operation = TokenOperation.RESTORING, error = null)
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
        val count = if (id == null) 0 else repository.get(id).historyTurnCount
        state.value = state.value.copy(initialized = true, restored = id != null, restoreFailed = false,
          probeRefreshRequired = false, historyTurnCount = count)
      } catch (e: CancellationException) { throw e
      } catch (e: Exception) {
        val lost = invalidId || (e as? ChatRequestException)?.code == "session_not_found"
        state.value = state.value.copy(restoreFailed = true, recoveryRequired = lost,
          error = if (lost) "Диалог недоступен. Начните новый диалог." else "Не удалось восстановить диалог. Повторите проверку.")
      } finally { state.value = state.value.copy(operation = TokenOperation.IDLE) }
    }
  }
  fun updateDraft(value: String) {
    if (!state.value.busy) state.value = state.value.copy(draft = value)
  }
  fun loadLongText() { if (state.value.ready) updateDraft(longFixture()) }

  private suspend fun ensureIdentity(): String {
    var id = state.value.sessionId
    if (id == null) {
      state.value = state.value.copy(operation = TokenOperation.CREATING)
      id = repository.create().sessionId
      identityPersisted = false
      state.value = state.value.copy(sessionId = id, identityKnown = true)
    }
    if (!identityPersisted) {
      state.value = state.value.copy(operation = TokenOperation.SAVING_ID)
      store.save(id)
      identityPersisted = true
    }
    return id
  }

  private fun observe(result: TokenTurnDto) {
    val old = state.value
    if (old.observations.any { it.id == result.attemptId }) return
    state.value = old.copy(observations = (old.observations +
      TokenObservation(old.nextNumber, result.attemptId, result.status, result)).takeLast(20),
      nextNumber = old.nextNumber + 1)
  }
  private fun unknownObservation() {
    val old = state.value
    state.value = old.copy(observations = (old.observations +
      TokenObservation(old.nextNumber, UUID.randomUUID().toString(), "unknown", null)).takeLast(20),
      nextNumber = old.nextNumber + 1)
  }

  fun send() { if (state.value.canSend) perform("send") }
  fun prepareOverflow() { if (state.value.ready) perform("prepare") }
  fun cancelPreparation() {
    if (!state.value.busy) state.value = state.value.copy(preparation = null)
  }
  fun expirePreparation(id: String) {
    if (!state.value.busy && state.value.preparation?.preparationId == id)
      state.value = state.value.copy(preparation = null, error = "Подготовка истекла. Подготовьте запрос снова.")
  }
  fun executeOverflow() {
    val p = state.value.preparation ?: return
    if (!state.value.ready) return
    if (p.expiresAt * 1000 <= System.currentTimeMillis()) {
      expirePreparation(p.preparationId); return
    }
    perform("execute")
  }
  private fun perform(kind: String) {
    val before = state.value
    val permission = before.preparation
    state.value = before.copy(operation = when (kind) {
      "prepare" -> TokenOperation.PREPARING
      "execute" -> TokenOperation.EXECUTING
      else -> TokenOperation.SENDING
    }, error = null, preparation = if (kind == "send") before.preparation else null)
    viewModelScope.launch {
      var networkStarted = false
      try {
        val id = ensureIdentity()
        state.value = state.value.copy(operation = when (kind) {
          "prepare" -> TokenOperation.PREPARING
          "execute" -> TokenOperation.EXECUTING
          else -> TokenOperation.SENDING
        })
        networkStarted = true
        val result = when (kind) {
          "prepare" -> repository.prepare(id)
          "execute" -> repository.execute(id, requireNotNull(permission).preparationId)
          else -> repository.send(id, before.draft)
        }
        check(result.sessionId == id)
        check(result.historyTurnCount == requireNotNull(before.historyTurnCount) + if (result.committed) 1 else 0)
        if (result.committed) {
          check(kind == "send" && result.status == "completed" && !result.reply.isNullOrBlank())
          state.value = state.value.copy(draft = "", messages = before.messages +
            listOf(ChatMessage(true, before.draft), ChatMessage(false, result.reply)),
            historyTurnCount = result.historyTurnCount, preparation = null)
        }
        state.value = state.value.copy(lastAttempt = result, error = result.error?.message,
          preparation = if (kind == "prepare") result.preparation else state.value.preparation)
        if (kind != "prepare") observe(result)
      } catch (e: CancellationException) { throw e
      } catch (e: Exception) {
        val code = (e as? ChatRequestException)?.code
        val lost = code == "session_not_found"
        val uncertain = networkStarted && code !in setOf("session_busy", "validation_error", "session_not_found")
        if (uncertain && kind != "prepare") unknownObservation()
        state.value = state.value.copy(
          recoveryRequired = lost || (uncertain && kind == "send"),
          probeRefreshRequired = uncertain && kind == "execute",
          error = when {
            !identityPersisted -> "Не удалось сохранить ID. Повторите действие; generation не выполнялась."
            lost -> "Диалог недоступен. Начните новый диалог."
            uncertain && kind == "send" -> "Результат отправки неизвестен. Начните новый диалог."
            uncertain && kind == "execute" -> "Результат probe неизвестен. Повтор запрещён; проверьте доступность диалога."
            else -> (e as? ChatRequestException)?.message ?: "Не удалось завершить действие."
          })
      } finally { state.value = state.value.copy(operation = TokenOperation.IDLE) }
    }
  }

  fun newConversation() {
    val before = state.value
    if (!before.canReset) return
    state.value = before.copy(operation = TokenOperation.RESETTING, error = null)
    viewModelScope.launch {
      try {
        if (!invalidId) before.sessionId?.let { repository.delete(it) }
        store.clear()
        invalidId = false
        identityPersisted = true
        state.value = TokenLabState(identityKnown = true, initialized = true, historyTurnCount = 0,
          generation = before.generation + 1)
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) {
        state.value = before.copy(recoveryRequired = true, error = "Не удалось сбросить диалог. Повторите «Новый диалог».")
      } finally { state.value = state.value.copy(operation = TokenOperation.IDLE) }
    }
  }
  companion object {
    const val KEY = "day_08_token_lab"
    fun longFixture() = (1..200).joinToString("\n") {
      "Запись ${it.toString().padStart(3, '0')}: учебный текст о стоимости повторной передачи истории."
    } + "\nОтветь кратко: принято."
    fun factory(repository: TokenLabRepository, store: CurrentSessionStore): ViewModelProvider.Factory =
      object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = TokenLabViewModel(repository, store) as T
      }
  }
}
