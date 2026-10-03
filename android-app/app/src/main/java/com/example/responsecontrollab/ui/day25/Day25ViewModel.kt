package com.example.responsecontrollab.ui.day25

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class Day25UiState(
  val initialized: Boolean = false, val identityKnown: Boolean = false,
  val sessionId: String? = null, val snapshot: Day25Snapshot? = null,
  val visibleTurns: List<Day25Turn> = emptyList(), val draft: String = "",
  val busy: Boolean = false, val recoveryRequired: Boolean = false,
  val error: String? = null, val notice: String? = null,
) {
  val canSend get() = initialized && identityKnown && !busy && !recoveryRequired && draft.isNotBlank() && draft.length <= 20000
  val canReset get() = identityKnown && !busy
}

class Day25ViewModel(private val repository: Day25Repository, private val identity: CurrentSessionStore): ViewModel() {
  private val mutable = MutableStateFlow(Day25UiState())
  val uiState = mutable.asStateFlow()
  private var persisted = false
  private var visibleAfter = 0
  private var pending: Pair<Int,String>? = null

  fun updateDraft(text: String) { mutable.value = mutable.value.copy(draft = text) }
  fun initialize() { if (!mutable.value.initialized && !mutable.value.busy) read() }

  fun read() {
    if (mutable.value.busy) return
    val cold = !mutable.value.initialized
    mutable.value = mutable.value.copy(busy = true, error = null)
    viewModelScope.launch {
      try {
        if (!mutable.value.identityKnown) {
          val id = identity.read()
          persisted = true
          mutable.value = mutable.value.copy(identityKnown = true, sessionId = id)
        }
        val id = mutable.value.sessionId
        if (id != null) {
          if (!validDay25Id(id)) throw Day25RequestException("malformed_session_id")
          val snapshot = repository.read(id)
          if (cold) visibleAfter = snapshot.revision
          val confirmedPending = pending?.let { (revision, message) ->
            snapshot.turns.any { it.turn == revision + 1 && it.user == message }
          } == true
          mutable.value = mutable.value.copy(snapshot = snapshot,
            visibleTurns = snapshot.turns.filter { it.turn > visibleAfter },
            draft = if (confirmedPending) "" else mutable.value.draft,
            notice = if (confirmedPending) "Ход подтверждён чтением; повторной отправки не было." else "Состояние прочитано с backend.")
          pending = null
        }
        mutable.value = mutable.value.copy(initialized = true, recoveryRequired = false)
      } catch (e: CancellationException) { fail("unknown"); throw e }
      catch (e: Exception) { fail((e as? Day25RequestException)?.code ?: "unknown") }
      finally { mutable.value = mutable.value.copy(initialized = true, busy = false) }
    }
  }

  fun send() {
    if (!mutable.value.canSend) return
    val message = mutable.value.draft
    mutable.value = mutable.value.copy(busy = true, error = null, notice = null)
    viewModelScope.launch {
      var dispatched = false
      try {
        if (mutable.value.sessionId == null) {
          val created = repository.create()
          mutable.value = mutable.value.copy(sessionId = created.session_id, snapshot = created)
          persisted = false
        }
        val id = requireNotNull(mutable.value.sessionId)
        if (!persisted) { identity.save(id); persisted = true }
        val revision = requireNotNull(mutable.value.snapshot).revision
        pending = revision to message
        dispatched = true
        val result = repository.send(id, Day25Message(message, revision))
        if (result.committed) {
          val snapshot = requireNotNull(result.state)
          mutable.value = mutable.value.copy(snapshot = snapshot,
            visibleTurns = snapshot.turns.filter { it.turn > visibleAfter }, draft = "", error = null)
          pending = null
        } else fail(result.error?.code ?: "unknown")
      } catch (e: CancellationException) { fail("unknown"); throw e }
      catch (e: Exception) {
        if (dispatched) fail((e as? Day25RequestException)?.code ?: "unknown")
        else mutable.value = mutable.value.copy(error = "Не удалось подготовить session. Сообщение не отправлено.")
      } finally { mutable.value = mutable.value.copy(busy = false) }
    }
  }

  fun reset() {
    if (!mutable.value.canReset) return
    mutable.value = mutable.value.copy(busy = true, error = null)
    viewModelScope.launch {
      try {
        val id = mutable.value.sessionId
        if (id != null && validDay25Id(id)) repository.delete(id)
        identity.clear()
        persisted = true; visibleAfter = 0; pending = null
        mutable.value = Day25UiState(initialized = true, identityKnown = true)
      } catch (e: CancellationException) { fail("unknown"); throw e }
      catch (e: Exception) { fail((e as? Day25RequestException)?.code ?: "unknown") }
      finally { mutable.value = mutable.value.copy(busy = false) }
    }
  }

  private fun fail(code: String) {
    val message = when (code) {
      "session_not_found" -> "Session не найдена. Можно явно сбросить сохранённый ID."
      "malformed_session_id" -> "Сохранённый ID некорректен. Выполните явный сброс."
      "unknown", "storage_unknown" -> "Исход операции неизвестен. Прочитайте состояние перед новой отправкой."
      else -> "Ход не подтверждён ($code). Прочитайте состояние; автоматического повтора нет."
    }
    mutable.value = mutable.value.copy(error = message, recoveryRequired = true)
  }

  companion object {
    const val KEY = "day25"
    fun factory(repository: Day25Repository, identity: CurrentSessionStore) = object: ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST")
      override fun <T: ViewModel> create(modelClass: Class<T>): T = Day25ViewModel(repository, identity) as T
    }
  }
}
