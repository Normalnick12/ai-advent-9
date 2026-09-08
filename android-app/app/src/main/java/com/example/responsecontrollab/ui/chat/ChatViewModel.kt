package com.example.responsecontrollab.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.ChatRepository
import com.example.responsecontrollab.data.ChatRequestException
import com.example.responsecontrollab.data.CurrentSessionStore
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChatMessage(val isUser: Boolean, val text: String)
enum class ChatOperation { IDLE, CREATING, SAVING_ID, RESTORING, SENDING, RESETTING }
enum class ChatRestoration { READY, REQUIRED, FAILED, LOST }
data class ChatUiState(
  val sessionId: String? = null,
  val messages: List<ChatMessage> = emptyList(),
  val draft: String = "",
  val pendingUser: String? = null,
  val operation: ChatOperation = ChatOperation.IDLE,
  val error: String? = null,
  val recoveryRequired: Boolean = false,
  val historyTurnCount: Int? = 0,
  val generation: Int = 0,
  val restoration: ChatRestoration = ChatRestoration.READY,
  val identityKnown: Boolean = true,
  val restored: Boolean = false,
) {
  val busy: Boolean get() = operation != ChatOperation.IDLE
  val canSend: Boolean get() = !busy && !recoveryRequired && restoration == ChatRestoration.READY &&
    draft.isNotBlank() && draft.length <= 20000
  val canReset: Boolean get() = !busy && identityKnown
  val canRetryRestore: Boolean get() = !busy && !recoveryRequired && restoration == ChatRestoration.FAILED
}

class ChatViewModel(
  private val repository: ChatRepository,
  private val currentSessionStore: CurrentSessionStore? = null,
) : ViewModel() {
  private val mutableState = MutableStateFlow(
    if (currentSessionStore == null) ChatUiState() else ChatUiState(
      restoration = ChatRestoration.REQUIRED, identityKnown = false, historyTurnCount = null,
    ),
  )
  val uiState = mutableState.asStateFlow()
  private var identityPersisted = currentSessionStore == null
  private var invalidStoredId = false

  fun initialize() {
    if (mutableState.value.restoration == ChatRestoration.REQUIRED && !mutableState.value.busy) restore()
  }

  fun retryRestore() {
    if (mutableState.value.canRetryRestore) restore()
  }

  private fun restore() {
    val store = currentSessionStore ?: return
    mutableState.value = mutableState.value.copy(operation = ChatOperation.RESTORING, error = null)
    viewModelScope.launch {
      try {
        if (!mutableState.value.identityKnown) {
          val id = store.read()
          identityPersisted = true
          invalidStoredId = id != null && !runCatching {
            UUID.fromString(id).toString() == id.lowercase()
          }.getOrDefault(false)
          mutableState.value = mutableState.value.copy(sessionId = id, identityKnown = true)
        }
        val id = mutableState.value.sessionId
        if (id == null) {
          mutableState.value = mutableState.value.copy(restoration = ChatRestoration.READY, historyTurnCount = 0)
        } else if (invalidStoredId) {
          mutableState.value = mutableState.value.copy(
            restoration = ChatRestoration.LOST, recoveryRequired = true,
            error = "Сохранённый диалог недоступен. Начните новый диалог.",
          )
        } else {
          val metadata = repository.getSession(id)
          check(metadata.sessionId == id && metadata.historyTurnCount >= 0)
          mutableState.value = mutableState.value.copy(
            restoration = ChatRestoration.READY, historyTurnCount = metadata.historyTurnCount,
            restored = true, recoveryRequired = false, generation = mutableState.value.generation + 1,
          )
        }
      } catch (error: CancellationException) {
        throw error
      } catch (error: Exception) {
        val lost = (error as? ChatRequestException)?.code == "session_not_found"
        mutableState.value = mutableState.value.copy(
          restoration = if (lost) ChatRestoration.LOST else ChatRestoration.FAILED,
          recoveryRequired = lost,
          error = when {
            lost -> "Диалог недоступен. Начните новый диалог."
            !mutableState.value.identityKnown -> "Не удалось прочитать сохранённый диалог. Повторите восстановление."
            else -> "Не удалось восстановить диалог. Повторите восстановление."
          },
        )
      } finally {
        mutableState.value = mutableState.value.copy(operation = ChatOperation.IDLE)
      }
    }
  }

  fun updateDraft(value: String) {
    if (!mutableState.value.busy) mutableState.value = mutableState.value.copy(draft = value)
  }

  fun send() {
    val before = mutableState.value
    if (!before.canSend) return
    mutableState.value = before.copy(
      operation = if (before.sessionId == null) ChatOperation.CREATING else ChatOperation.SENDING,
      pendingUser = before.draft, error = null,
    )
    viewModelScope.launch {
      var sending = false
      var savingIdentity = false
      try {
        val id = before.sessionId ?: repository.createSession().sessionId.also {
          identityPersisted = currentSessionStore == null
          mutableState.value = mutableState.value.copy(sessionId = it)
        }
        if (currentSessionStore != null && !identityPersisted) {
          savingIdentity = true
          mutableState.value = mutableState.value.copy(operation = ChatOperation.SAVING_ID)
          currentSessionStore.save(id)
          identityPersisted = true
          savingIdentity = false
        }
        mutableState.value = mutableState.value.copy(operation = ChatOperation.SENDING)
        sending = true
        val result = repository.sendMessage(id, before.draft)
        if (result.status == "completed") {
          check(result.historyTurnCount == requireNotNull(before.historyTurnCount) + 1)
          mutableState.value = mutableState.value.copy(
            messages = before.messages + listOf(ChatMessage(true, before.draft), ChatMessage(false, requireNotNull(result.reply))),
            draft = "", historyTurnCount = result.historyTurnCount,
          )
        } else {
          check(result.historyTurnCount == before.historyTurnCount)
          mutableState.value = mutableState.value.copy(error = result.error?.message ?: "Не удалось получить ответ.")
        }
      } catch (error: CancellationException) {
        throw error
      } catch (error: Exception) {
        val known = error as? ChatRequestException
        val lost = known?.code == "session_not_found"
        val uncertain = sending && known?.code !in setOf("session_busy", "validation_error", "session_not_found")
        mutableState.value = mutableState.value.copy(
          recoveryRequired = lost || uncertain,
          error = when {
            savingIdentity -> "Не удалось сохранить диалог. Повторите отправку."
            lost -> "Диалог недоступен. Начните новый диалог."
            uncertain -> "Результат отправки неизвестен. Начните новый диалог."
            else -> known?.message ?: "Не удалось создать диалог. Попробуйте ещё раз."
          },
        )
      } finally {
        mutableState.value = mutableState.value.copy(operation = ChatOperation.IDLE, pendingUser = null)
      }
    }
  }

  fun newConversation() {
    val before = mutableState.value
    if (!before.canReset) return
    if (before.sessionId == null) {
      mutableState.value = ChatUiState(generation = before.generation + 1)
      return
    }
    mutableState.value = before.copy(operation = ChatOperation.RESETTING, error = null)
    viewModelScope.launch {
      try {
        if (!invalidStoredId) repository.deleteSession(before.sessionId)
        currentSessionStore?.clear()
        identityPersisted = true
        invalidStoredId = false
        mutableState.value = ChatUiState(generation = before.generation + 1)
      } catch (error: CancellationException) {
        throw error
      } catch (_: Exception) {
        mutableState.value = before.copy(recoveryRequired = true, error = "Не удалось сбросить диалог. Повторите «Новый диалог».")
      } finally {
        mutableState.value = mutableState.value.copy(operation = ChatOperation.IDLE)
      }
    }
  }

  companion object {
    const val DAY_06_KEY = "day_06_chat"
    const val DAY_07_KEY = "day_07_chat"

    fun factory(
      repository: ChatRepository, currentSessionStore: CurrentSessionStore? = null,
    ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST")
      override fun <T : ViewModel> create(modelClass: Class<T>): T = ChatViewModel(repository, currentSessionStore) as T
    }
  }
}
