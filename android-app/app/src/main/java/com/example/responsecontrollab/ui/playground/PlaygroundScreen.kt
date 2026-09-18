package com.example.responsecontrollab.ui.playground

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar
import com.example.responsecontrollab.ui.chat.ChatBubble
import com.example.responsecontrollab.ui.chat.ChatMessage
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*

private val rawDebugJson = Json { prettyPrint=true; encodeDefaults=true }

@Composable
fun PlaygroundScreen(vm: PlaygroundViewModel, onBack: () -> Unit) {
  val u by vm.uiState.collectAsState()
  LaunchedEffect(Unit) { vm.load() }
  val pages = rememberSaveableStateHolder()
  val back = { if (u.page == "main") onBack() else vm.back() }
  BackHandler(enabled=u.page != "main") { vm.back() }
  Scaffold(topBar={ LearningDayTopBar(LearningDay.AGENT_PLAYGROUND, back) },
    contentWindowInsets=WindowInsets.safeDrawing) { padding ->
    pages.SaveableStateProvider(u.page) {
      val scroll = rememberLazyListState()
      LazyColumn(state=scroll, modifier=Modifier.fillMaxSize().padding(padding)
        .consumeWindowInsets(padding).imePadding().testTag("playground_scroll"),
        contentPadding=PaddingValues(16.dp), verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item {
          Text("Agent Playground", style=MaterialTheme.typography.headlineSmall)
          if (u.page != "main") TextButton(onClick={ vm.back() }, modifier=Modifier.testTag("playground_back")) { Text("Назад") }
          if (u.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
          u.error?.let { Text(it, color=MaterialTheme.colorScheme.error, modifier=Modifier.testTag("playground_error")) }
          if (u.reconciliation || !u.loaded) {
            Button(onClick=vm::refresh, enabled=!u.busy, modifier=Modifier.testTag("playground_refresh")) { Text("Прочитать состояние") }
          }
        }
        when (u.page) {
          "setup" -> item { Setup(u, vm) }
          "raw" -> item {
            Text("Raw Debug — diagnostic / untrusted", style=MaterialTheme.typography.titleMedium)
            Text("Эти данные не используются как источник следующего Send.")
            val r = u.selectedReceipt
            Text(if (r == null) "Диагностика попытки недоступна" else
              rawDebugJson.encodeToString(r),
              modifier=Modifier.testTag("playground_raw"))
          }
          "inspector" -> {
            item { InspectorSummary(u, vm) }
            val r = u.selectedReceipt
            if (r != null) {
              items(listOf("Memory", "Profile", "Task State", "Invariants", "Request",
                "Validation / Enforcement", "Lifecycle", "Conversation commit"), key={ it }) { section ->
                Section(section, section in u.expanded, { vm.toggle(section) }) { InspectorSection(section, r, u.catalog) }
              }
              item {
                Text("Current — сейчас", style=MaterialTheme.typography.titleMedium)
                Text("Этап: ${u.current?.stage_label ?: "недоступен"} · Profile: ${u.current?.profile?.name ?: "недоступен"}")
                Text("Текущие данные не заменяют Used in this turn.", style=MaterialTheme.typography.bodySmall)
              }
            }
          }
          else -> {
            item { MainHeader(u, vm) }
            u.receipts[u.latest]?.let { r ->
              item { OperationCard(r, u.catalog, { vm.inspect(r.attempt_id) }, vm::dismissResult) }
            }
            val current = u.current
            items(current?.memory?.short_term ?: emptyList(), key={ "${current?.memory?.session_id}:${it.position}" }) { message ->
              Column {
                ChatBubble(ChatMessage(message.role == "user", message.content))
                if (message.role == "assistant") TextButton(onClick={
                  vm.inspectPair(requireNotNull(current?.memory).session_id, message.position - 1)
                }, modifier=Modifier.testTag("playground_pair_${message.position}")) { Text("Inspector ответа") }
              }
            }
            u.pending?.let { pending -> item {
              Card { Text("Ожидает подтверждения сохранения:\n$pending", Modifier.padding(12.dp).testTag("playground_pending")) }
            } }
            if (current?.can_send == true) item {
              OutlinedTextField(value=u.draft, onValueChange=vm::draft, enabled=!u.busy,
                label={ Text("Обсудить задачу") }, minLines=2, maxLines=8,
                modifier=Modifier.fillMaxWidth().testTag("playground_query"))
              Button(onClick=vm::send, enabled=u.writable && u.draft.isNotBlank(),
                modifier=Modifier.testTag("playground_send")) { Text("Отправить") }
              if (current.task_state?.status == "PAUSED") Text("Уточнение не возобновляет задачу.")
            }
            item { MainActions(u, vm) }
          }
        }
      }
    }
  }
}

@Composable
private fun MainHeader(u: PlaygroundUi, vm: PlaygroundViewModel) {
  val c = u.current
  Text(u.catalog?.task_title ?: "Checkout", style=MaterialTheme.typography.titleLarge)
  if (c?.task_state != null) {
    Text(when {
      c.task_state.is_terminal -> "Задача завершена"
      c.task_state.status == "PAUSED" -> "Задача приостановлена"
      else -> "Этап: ${c.stage_label}"
    }, style=MaterialTheme.typography.titleMedium, modifier=Modifier.testTag("playground_stage"))
    Text(c.next_action)
  }
  c?.policy?.values?.let { PolicySummary(it) }
  if (c?.profile != null) {
    Text("Profile: ${c.profile.name}")
    Choices(u.catalog?.profiles?.map { it.id to it.name } ?: emptyList(),
      selected=u.catalog?.profiles?.find { it.name == c.profile.name }?.id ?: "",
      enabled=u.writable && c.ready, onSelect=vm::selectProfile, tag="playground_profile")
  }
  if (c?.setup?.status == "pending") {
    Text("Подготовка не завершена. Сохранённые настройки:")
    PolicySummary(c.setup.configuration.policy)
    Text("Profile: ${c.setup.profile_fields.name}")
    Text("Недостающие компоненты: " + c.readiness.filterValues { !it }.keys.joinToString { readinessLabel(it) })
    Button(onClick=vm::completeSetup, enabled=u.writable, modifier=Modifier.testTag("playground_complete")) { Text("Завершить подготовку") }
  } else if (c?.memory == null && u.loaded) {
    Text("Создайте задачу и подтвердите её настройки.")
    Button(onClick=vm::openSetup, enabled=u.writable, modifier=Modifier.testTag("playground_new_task")) { Text("Новая задача") }
  }
  if (c?.source_error != null) Text("Источники задачи недоступны или несовместимы. Прочитайте состояние ещё раз.")
}

private fun readinessLabel(key: String) = when (key) {
  "memory_ready" -> "память"; "profile_ready" -> "Profile"; "state_ready" -> "этап задачи"
  "policy_ready" -> "ограничения"; "setup_ready" -> "подтверждение подготовки"; else -> key
}

@Composable
private fun MainActions(u: PlaygroundUi, vm: PlaygroundViewModel) {
  val c = u.current ?: return
  Column(verticalArrangement=Arrangement.spacedBy(6.dp)) {
    c.actions.forEach { action ->
      OutlinedButton(onClick={ vm.event(action.event) }, enabled=u.writable && c.ready,
        modifier=Modifier.fillMaxWidth().testTag("playground_event_${action.event}")) { Text(action.label) }
    }
    if (c.memory != null && c.setup?.status != "pending") {
      Section("Другие действия", "actions" in u.expanded, { vm.toggle("actions") }) {
        TextButton(onClick=vm::openSetup, enabled=u.writable && c.ready, modifier=Modifier.testTag("playground_new_task")) { Text("Новая задача") }
        TextButton(onClick=vm::newConversation, enabled=u.writable && c.ready,
          modifier=Modifier.testTag("playground_new_conversation")) { Text("Новый разговор — история этой задачи останется отдельно") }
        TextButton(onClick=vm::refresh, enabled=!u.busy) { Text("Прочитать состояние") }
      }
    }
    c.educational_event?.let { event ->
      Section("Проверка запрещённого перехода", "educational" in u.expanded, { vm.toggle("educational") }) {
        Text("Учебная проверка: попробовать пропустить обязательный этап.")
        OutlinedButton(onClick={ vm.event(event, educational=true) }, enabled=u.writable,
          modifier=Modifier.testTag("playground_forbidden")) {
          Text(u.catalog?.event_labels?.get(event) ?: event)
        }
      }
    }
  }
}

@Composable
private fun PolicySummary(policy: CodingPolicyValues) {
  Text("Ограничения задачи: ${policy.required_architecture} · ${policy.required_ui_toolkit} · ${policy.required_async_model}. " +
    "Подтверждение оплаты: ${if (policy.payment_confirmation_required) "обязательно" else "не требуется"}.")
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Choices(values: List<Pair<String,String>>, selected: String, enabled: Boolean,
  onSelect: (String) -> Unit, tag: String) {
  FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
    values.forEach { (id, label) ->
      FilterChip(selected=selected == id, onClick={ onSelect(id) }, enabled=enabled,
        label={ Text(label) }, modifier=Modifier.testTag("${tag}_$id"))
    }
  }
}

@Composable
private fun Setup(u: PlaygroundUi, vm: PlaygroundViewModel) {
  val config = u.setupDraft ?: return
  Column(verticalArrangement=Arrangement.spacedBy(12.dp)) {
    Text("Новая Coding Agent задача", style=MaterialTheme.typography.titleLarge)
    Text(u.catalog?.task_title ?: "Checkout")
    Text("Требования → Согласование → Реализация → Проверка → Завершение. Можно явно вернуть план к требованиям или проверку к реализации.")
    Text("Profile")
    Choices(u.catalog?.profiles?.map { it.id to it.name } ?: emptyList(), config.profile_preset, !u.busy,
      { vm.setupDraft(config.copy(profile_preset=it)) }, "playground_setup_profile")
    val policy = config.policy
    listOf("required_architecture" to "Архитектура", "required_ui_toolkit" to "UI toolkit",
      "required_async_model" to "Асинхронная модель").forEach { (key, label) ->
      Text(label)
      val values = (u.catalog?.policy_options?.get(key) as? JsonArray)?.map { it.jsonPrimitive.content } ?: emptyList()
      val selected = when (key) {
        "required_architecture" -> policy.required_architecture
        "required_ui_toolkit" -> policy.required_ui_toolkit
        else -> policy.required_async_model
      }
      Choices(values.map { it to it }, selected, !u.busy, {
        vm.setupDraft(config.copy(policy=when (key) {
          "required_architecture" -> policy.copy(required_architecture=it)
          "required_ui_toolkit" -> policy.copy(required_ui_toolkit=it)
          else -> policy.copy(required_async_model=it)
        }))
      }, "playground_setup_$key")
    }
    Row {
      Switch(checked=policy.payment_confirmation_required,
        onCheckedChange={ vm.setupDraft(config.copy(policy=policy.copy(payment_confirmation_required=it))) },
        enabled=!u.busy, modifier=Modifier.testTag("playground_setup_payment"))
      Text("Обязательное подтверждение оплаты", Modifier.padding(12.dp).weight(1f))
    }
    Text("Ограничения сохраняются для всей задачи. Для других ограничений создайте новую задачу.")
    if (!u.review) Button(onClick=vm::review, enabled=u.writable, modifier=Modifier.testTag("playground_review")) { Text("Проверить настройки") }
    else {
      Card { Column(Modifier.padding(12.dp)) {
        Text("Подтвердите создание задачи")
        Text("Profile: ${u.catalog?.profiles?.find { it.id == config.profile_preset }?.name}")
        PolicySummary(policy)
        Text("Начальный этап: Требования. Создание не вызывает модель.")
      } }
      Button(onClick=vm::create, enabled=u.writable, modifier=Modifier.testTag("playground_confirm")) { Text("Создать задачу") }
    }
    TextButton(onClick=vm::back, enabled=!u.busy, modifier=Modifier.testTag("playground_cancel")) { Text("Отмена") }
  }
}

@Composable
private fun OperationCard(r: PlaygroundReceipt, catalog: PlaygroundCatalog?, inspect: () -> Unit, dismiss: () -> Unit) {
  val summary = summary(r)
  Card(modifier=Modifier.fillMaxWidth().testTag("playground_result")) {
    Column(Modifier.padding(12.dp), verticalArrangement=Arrangement.spacedBy(6.dp)) {
      Text(summary.outcome, style=MaterialTheme.typography.titleMedium)
      r.explanation?.let { Text(it) }
      if (r.operation == "lifecycle") {
        Text("${catalog?.nodes?.get(r.before?.state_id) ?: "?"} → ${catalog?.event_labels?.get(r.event) ?: r.event} → ${catalog?.nodes?.get(r.after?.state_id) ?: "исход неизвестен"}")
      }
      Text("Provider: ${summary.provider}")
      Text("Conversation: ${summary.conversation}")
      TextButton(onClick=inspect, modifier=Modifier.testTag("playground_inspect")) { Text("Inspector операции") }
      TextButton(onClick=dismiss) { Text("Закрыть результат") }
    }
  }
}

@Composable
private fun InspectorSummary(u: PlaygroundUi, vm: PlaygroundViewModel) {
  val r = u.selectedReceipt
  Text("Inspector", style=MaterialTheme.typography.headlineSmall)
  if (r == null) { Text("Диагностика попытки недоступна", Modifier.testTag("playground_unavailable")); return }
  val s = summary(r)
  Column(Modifier.testTag("playground_summary"), verticalArrangement=Arrangement.spacedBy(6.dp)) {
    Text(s.outcome); Text("Provider: ${s.provider}"); Text("Conversation: ${s.conversation}")
    Text(s.coverage)
    Text("Used in this turn — в выбранной операции", style=MaterialTheme.typography.titleMedium)
    Text("Этап: ${u.catalog?.nodes?.get(r.sources?.state?.state_id ?: r.before?.state_id) ?: "недоступен"}")
    Text("Profile: ${r.sources?.profile?.name ?: "Not required — не требовался"}")
    if (r.operation == "lifecycle") LifecycleEvidence(r, u.catalog)
    TextButton(onClick={ vm.page("raw") }, modifier=Modifier.testTag("playground_open_raw")) { Text("Raw Debug") }
  }
}

@Composable
private fun Section(title: String, expanded: Boolean, toggle: () -> Unit, body: @Composable () -> Unit) {
  Card(Modifier.fillMaxWidth()) {
    Column(Modifier.padding(12.dp), verticalArrangement=Arrangement.spacedBy(8.dp)) {
      TextButton(onClick=toggle, modifier=Modifier.testTag("playground_section_$title")) { Text((if (expanded) "− " else "+ ") + title) }
      if (expanded) body()
    }
  }
}

@Composable
private fun LifecycleEvidence(r: PlaygroundReceipt, catalog: PlaygroundCatalog?) {
  Text("Before: ${catalog?.nodes?.get(r.before?.state_id) ?: "Unavailable"} · revision ${r.before?.revision}")
  Text("Event: ${catalog?.event_labels?.get(r.event) ?: r.event}")
  Text("After: ${catalog?.nodes?.get(r.after?.state_id) ?: "Unknown"} · revision ${r.after?.revision}")
  Text("Outcome: ${outcomeLabel(r.outcome)}")
  r.explanation?.let { Text(it) }
}

@Composable
private fun InspectorSection(section: String, r: PlaygroundReceipt, catalog: PlaygroundCatalog?) {
  val s = r.sources
  when (section) {
    "Memory" -> if (s == null) Text(evidenceLabel("not_required")) else {
      Text("Выбрано сообщений: ${s.memory.short_term.size}; полных пар: ${s.memory.short_term.size / 2}")
      Text("Working: " + s.selection.selected_working.entries.joinToString { "${it.key}: ${it.value}" })
      Text("Long-term: " + s.selection.selected_long_term.entries.joinToString { "${it.key}: ${it.value}" }.ifEmpty { "пусто" })
      Text("Исключено: " + s.selection.excluded.joinToString { "${it.key}: ${it.reason}" }.ifEmpty { "нет" })
      Text("Inactive tasks: ${s.selection.inactive_tasks.size}; inactive conversations: ${s.selection.inactive_sessions.size}")
    }
    "Profile" -> if (s == null) Text(evidenceLabel("not_required")) else {
      Text("${s.profile.name}; язык ${s.profile.language}; тон ${s.profile.tone}; объём ${s.profile.verbosity}")
      Text(r.profile_section ?: evidenceLabel("unavailable"))
    }
    "Task State" -> {
      Text("Позиция: ${s?.state?.state_id ?: r.before?.state_id}; revision ${s?.state?.revision ?: r.before?.revision}")
      Text("Send не меняет этап. Lifecycle выполняется отдельным действием.")
      r.state_section?.let { Text(it) }
    }
    "Invariants" -> if (s == null) Text(evidenceLabel("not_required")) else {
      PolicySummary(s.policy.values)
      s.rules.forEach { Text(it["description"]?.jsonPrimitive?.content ?: "") }
    }
    "Request" -> {
      Text("Сборка: ${evidenceLabel(r.assembly_status)}")
      Text("Actual dispatched input: ${if (r.actual_request == null) "отсутствует" else "зафиксирован на границе клиента"}")
      Text("Сообщений отправлено: ${(r.actual_request?.get("messages") as? JsonArray)?.size ?: "Not attempted"}")
      Text("Точные messages/config доступны в Raw Debug.")
    }
    "Validation / Enforcement" -> {
      Text("Precheck: ${evidenceLabel(r.precheck_status)}")
      Text("Candidate: ${r.candidate_preparation ?: "Not required"}")
      val validation = r.turn?.validation
      Text("Checks: ${evidenceLabel(validation?.get("status")?.jsonPrimitive?.content)}")
      (validation?.get("checked_rules") as? JsonArray)?.forEach { Text(it.jsonObject["description"]?.jsonPrimitive?.content ?: "") }
      (validation?.get("violations") as? JsonArray)?.forEach { Text("Нарушение: " + (it.jsonObject["reason"]?.jsonPrimitive?.content ?: "")) }
      Text(summary(r).coverage)
    }
    "Lifecycle" -> if (r.operation == "lifecycle") LifecycleEvidence(r, catalog) else Text("Not applicable — Send не применяет event.")
    "Conversation commit" -> {
      Text("Acceptance: ${r.turn?.decision ?: "Not applicable"}")
      Text("Commit: ${evidenceLabel(r.turn?.commit_status ?: r.conversation_commit)}")
      Text("Связь с парой: ${r.pair_position?.toString() ?: "не подтверждена / не применимо"}")
    }
  }
}
