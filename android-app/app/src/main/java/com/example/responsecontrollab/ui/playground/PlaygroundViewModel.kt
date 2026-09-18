package com.example.responsecontrollab.ui.playground

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class PlaygroundUi(
  val loaded: Boolean = false, val busy: Boolean = false, val reconciliation: Boolean = false,
  val current: PlaygroundCurrent? = null, val catalog: PlaygroundCatalog? = null, val error: String? = null,
  val draft: String = "", val pending: String? = null, val page: String = "main",
  val setupDraft: PlaygroundConfiguration? = null, val review: Boolean = false,
  val receipts: Map<String,PlaygroundReceipt> = emptyMap(), val latest: String? = null,
  val selected: String? = null, val expanded: Set<String> = emptySet(),
) {
  val writable get() = loaded && !busy && !reconciliation && current?.busy != true
  val selectedReceipt get() = receipts[selected]
}

class PlaygroundViewModel(private val repository: PlaygroundRepository): ViewModel() {
  private val state = MutableStateFlow(PlaygroundUi())
  val uiState = state.asStateFlow()
  fun load() { if (!state.value.loaded && !state.value.busy) refresh() }
  private fun accept(current: PlaygroundCurrent) {
    state.value = state.value.copy(current=current, reconciliation=current.busy || current.reconciliation_required)
  }
  fun refresh() {
    if (state.value.busy) return
    state.value = state.value.copy(busy=true)
    viewModelScope.launch {
      try {
        val catalog = state.value.catalog ?: repository.catalog()
        accept(repository.current())
        state.value = state.value.copy(catalog=catalog, loaded=true, error=null)
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) {
        state.value = state.value.copy(reconciliation=true, error="Не удалось прочитать backend. Доступно повторное чтение.")
      } finally { state.value = state.value.copy(busy=false) }
    }
  }
  private fun action(block: suspend () -> Unit) {
    if (!state.value.writable) return
    val previousMemory = state.value.current?.memory
    state.value = state.value.copy(busy=true, error=null)
    viewModelScope.launch {
      try { block()
      } catch (e: CancellationException) { throw e
      } catch (_: Exception) {
        state.value = state.value.copy(reconciliation=true,
          error="Исход операции не подтверждён. Выполняется чтение; операция не повторяется.")
        try {
          accept(repository.current())
          state.value.pending?.let { clearConfirmedDraft(previousMemory, it) }
        }
        catch (e: CancellationException) { throw e }
        catch (_: Exception) { /* Explicit read retry; no replay. */ }
      } finally { state.value = state.value.copy(busy=false, pending=null) }
    }
  }
  private fun clearConfirmedDraft(before: MemoryStateDto?, query: String) {
    val after = state.value.current?.memory ?: return
    if (before == null || after.session_id != before.session_id) return
    val oldSize = before.short_term.size
    if (after.short_term.size == oldSize + 2 && after.short_term.take(oldSize) == before.short_term &&
      after.short_term[oldSize].role == "user" && after.short_term[oldSize].content == query &&
      after.short_term[oldSize + 1].role == "assistant") state.value = state.value.copy(draft="")
  }
  private fun received(result: PlaygroundOperation) {
    val r = result.receipt
    val receipts = LinkedHashMap(state.value.receipts)
    receipts[r.attempt_id] = r
    while (receipts.size > 50) receipts.remove(receipts.keys.first())
    result.current?.let(::accept)
    state.value = state.value.copy(receipts=receipts.toMap(), latest=r.attempt_id,
      reconciliation=result.current == null || state.value.reconciliation,
      error=if (r.outcome == "technical_error") "Техническая ошибка. Подробности в Inspector." else null)
  }
  fun draft(value: String) { if (!state.value.busy) state.value = state.value.copy(draft=value.take(20000)) }
  fun send() {
    val u = state.value
    val c = u.current ?: return
    val ref = c.reference ?: return
    if (!u.writable || !c.can_send || u.draft.isBlank()) return
    val query = u.draft
    action {
      state.value = state.value.copy(pending=query)
      val result = repository.send(ref.send(query))
      received(result)
      if (result.receipt.turn?.commit_status == "committed")
        state.value = state.value.copy(draft="")
      else if (result.receipt.turn?.commit_status == "unknown") clearConfirmedDraft(c.memory, query)
    }
  }
  fun event(name: String, educational: Boolean = false) {
    val c = state.value.current ?: return
    val ref = c.reference ?: return
    if (!c.ready || (if (educational) c.educational_event != name else c.actions.none { it.event == name })) return
    action { received(repository.event(ref.event(name))) }
  }
  fun selectProfile(preset: String) {
    val ref = state.value.current?.reference ?: return
    if (state.value.catalog?.profiles?.none { it.id == preset } != false) return
    action { accept(repository.profile(ref.profile(preset))) }
  }
  fun newConversation() {
    val ref = state.value.current?.reference ?: return
    action { accept(repository.conversation(ref)); state.value = state.value.copy(draft="") }
  }
  fun openSetup() {
    val u = state.value
    if (!u.writable || u.current?.setup?.status == "pending") return
    state.value = u.copy(page="setup", setupDraft=u.catalog?.defaults, review=false)
  }
  fun setupDraft(value: PlaygroundConfiguration) {
    if (!state.value.busy) state.value = state.value.copy(setupDraft=value, review=false)
  }
  fun review() { if (state.value.setupDraft != null) state.value = state.value.copy(review=true) }
  fun create() {
    val u = state.value
    val config = u.setupDraft ?: return
    if (!u.review) return
    action {
      accept(repository.create(PlaygroundCreate(config, u.current?.reference)))
      state.value = state.value.copy(page="main", setupDraft=null, review=false, draft="")
    }
  }
  fun completeSetup() {
    val setup = state.value.current?.setup?.takeIf { it.status == "pending" } ?: return
    action { accept(repository.complete(PlaygroundComplete(setup.task_id))) }
  }
  fun inspect(attempt: String?) {
    state.value = state.value.copy(page="inspector", selected=attempt, expanded=emptySet())
  }
  fun inspectPair(session: String, position: Int) = inspect(state.value.receipts.values.lastOrNull {
    it.session_id == session && it.pair_position == position }?.attempt_id)
  fun page(value: String) { state.value = state.value.copy(page=value) }
  fun back() {
    state.value = when (state.value.page) {
      "raw" -> state.value.copy(page="inspector")
      else -> state.value.copy(page="main", review=false)
    }
  }
  fun toggle(section: String) {
    val expanded = state.value.expanded
    state.value = state.value.copy(expanded=if (section in expanded) expanded-section else expanded+section)
  }
  fun dismissResult() { state.value = state.value.copy(latest=null) }
  companion object {
    fun factory(repository: PlaygroundRepository) = object: ViewModelProvider.Factory {
      @Suppress("UNCHECKED_CAST")
      override fun <T: ViewModel> create(modelClass: Class<T>): T = PlaygroundViewModel(repository) as T
    }
  }
}
