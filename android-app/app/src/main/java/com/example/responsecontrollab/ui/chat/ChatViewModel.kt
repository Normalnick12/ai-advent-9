package com.example.responsecontrollab.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.ChatRepository
import com.example.responsecontrollab.data.ChatRequestException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChatMessage(val isUser: Boolean, val text: String)
enum class ChatOperation { IDLE, CREATING, SENDING, RESETTING }
data class ChatUiState(
  val sessionId: String? = null,
  val messages: List<ChatMessage> = emptyList(),
  val draft: String = "",
  val pendingUser: String? = null,
  val operation: ChatOperation = ChatOperation.IDLE,
  val error: String? = null,
  val recoveryRequired: Boolean = false,
  val historyTurnCount: Int = 0,
  val generation: Int = 0,
) {
  val busy: Boolean get() = operation != ChatOperation.IDLE
  val canSend: Boolean get() = !busy && !recoveryRequired && draft.isNotBlank() && draft.length <= 20000
}

class ChatViewModel(private val repository: ChatRepository) : ViewModel() {
  private val mutableState = MutableStateFlow(ChatUiState())
  val uiState = mutableState.asStateFlow()

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
      try {
        val id = before.sessionId ?: repository.createSession().sessionId.also {
          mutableState.value = mutableState.value.copy(sessionId = it, operation = ChatOperation.SENDING)
        }
        sending = true
        val result = repository.sendMessage(id, before.draft)
        if (result.status == "completed") {
          check(result.historyTurnCount == before.historyTurnCount + 1)
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
            lost -> "Диалог потерян после перезапуска сервера. Начните новый диалог."
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
    if (before.busy) return
    if (before.sessionId == null) {
      mutableState.value = ChatUiState(generation = before.generation + 1)
      return
    }
    mutableState.value = before.copy(operation = ChatOperation.RESETTING, error = null)
    viewModelScope.launch {
      try {
        repository.deleteSession(before.sessionId)
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
    fun factory(repository: ChatRepository): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST")
      override fun <T : ViewModel> create(modelClass: Class<T>): T = ChatViewModel(repository) as T
    }
  }
}
