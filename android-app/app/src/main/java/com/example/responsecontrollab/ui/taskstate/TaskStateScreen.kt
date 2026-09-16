package com.example.responsecontrollab.ui.taskstate

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val pretty=Json { prettyPrint=true; encodeDefaults=true }

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TaskStateScreen(vm: TaskStateViewModel,onBack: ()->Unit) {
  val u by vm.uiState.collectAsState()
  LaunchedEffect(Unit) { vm.load() }
  BackHandler(u.page!="main") { vm.page("main") }
  val enabled=u.loaded && !u.busy && !u.recovery && u.current?.busy!=true
  val c=u.current; val memory=c?.memory; val s=c?.task_state
  val pages=rememberSaveableStateHolder()
  Scaffold(topBar={ LearningDayTopBar(LearningDay.TASK_STATE) { if(u.page=="main") onBack() else vm.page("main") } }) { padding ->
    pages.SaveableStateProvider(u.page) {
      LazyColumn(state=rememberLazyListState(),modifier=Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
        .imePadding().testTag("task_scroll"),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item {
          if(u.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
          u.error?.let { Text(it,color=MaterialTheme.colorScheme.error) }
          TextButton(onClick=vm::refresh,enabled=!u.busy) { Text("Прочитать backend") }
          FlowRow {
            for((page,label) in listOf("main" to "Задача","setup" to "Подготовка","inspector" to "Inspector")) {
              FilterChip(selected=u.page==page,onClick={vm.page(page)},label={Text(label)},modifier=Modifier.testTag("task_page_$page"))
            }
          }
        }
        when(u.page) {
          "main" -> {
            item {
              Text(memory?.working?.get("task")?:"Задача не подготовлена",style=MaterialTheme.typography.titleLarge)
              Text("Working: ${memory?.working?.filterKeys { it!="task" }?:emptyMap<String,String>()}")
              Text("Long-term: ${memory?.long_term?:emptyMap<String,String>()}")
              Text("Profile: ${c?.active()?.name?:"не выбран"}")
              Text("Generation calls: ${c?.generation_calls?:0}")
              if(c?.ready!=true) Text("Завершите подготовку: Memory, Profile и Task State.",Modifier.testTag("task_not_ready"))
            }
            item {
              Card(Modifier.fillMaxWidth().testTag("task_state_card")) { Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                Text("Task State",style=MaterialTheme.typography.titleLarge)
                if(s==null) Text(c?.state_error?:"Состояние отсутствует") else {
                  Text("Phase: ${s.phase}\nStep: ${s.step}\nStatus: ${s.status}")
                  Text("${if(s.status=="PAUSED") "После Resume" else "Expected action"}: ${s.expected_action}")
                  if(s.status=="PAUSED") Text("Можно обсуждать задачу. Workflow продолжится только после Resume.")
                  if(s.is_terminal) Text("Workflow завершён.")
                  FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    // Events come from the backend. Android has no transition table.
                    s.allowed_events.forEach { event ->
                      Button(onClick={vm.event(event)},enabled=enabled && c.ready,modifier=Modifier.testTag("task_event_$event")) {
                        Text(when(event) { "PAUSE" -> "Pause"; "RESUME" -> "Resume"; else -> event.replace('_',' ') })
                      }
                    }
                  }
                }
              } }
            }
            if(memory!=null) item {
              Text("Session ${memory.session_id.take(8)} · ${memory.short_term.size/2} turns",Modifier.testTag("task_session"))
              FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick={vm.lifecycle("new-conversation")},enabled=enabled,modifier=Modifier.testTag("task_new_conversation")) { Text("New Conversation") }
                OutlinedButton(onClick={vm.lifecycle("new-task")},enabled=enabled) { Text("New Task") }
              }
              Text("New Conversation сохраняет Working, Profile и Task State.")
            }
            item {
              OutlinedTextField(u.message,vm::message,label={Text("Сообщение")},enabled=enabled && c?.ready==true,
                modifier=Modifier.fillMaxWidth().testTag("task_message"))
              Button(onClick=vm::send,enabled=enabled && c?.ready==true && u.message.isNotBlank(),modifier=Modifier.testTag("task_send")) { Text("Отправить") }
            }
            u.latest?.let { o -> item {
              Text("Последний ответ · ${o.outcome.status} · committed=${o.conversation_committed}")
              Text("Session ${o.memory.session_id.take(8)} · ${if(o.memory.session_id==memory?.session_id) "текущая" else "предыдущая conversation"}")
              SelectionContainer { Text(o.outcome.reply?:o.outcome.error_code?:o.outcome.incomplete_reason?:"Ответ недоступен") }
              TextButton(onClick={vm.page("inspector")}) { Text("Actual request и observations") }
            } }
          }
          "setup" -> {
            item {
              Text("Явная подготовка",style=MaterialTheme.typography.titleLarge)
              Text("Setup и events не вызывают модель. Probe и обычный Send вызывают.")
              if(memory==null) Button(onClick=vm::initialize,enabled=enabled) { Text("Создать задачу Day 13") }
              else {
                Text("Memory ready: ${c.readiness.memory_ready}\nProfile ready: ${c.readiness.profile_ready}\nTask State ready: ${c.readiness.task_state_ready}")
                if(s==null && c.state_error==null) Button(onClick=vm::initializeState,enabled=enabled) { Text("Создать State текущей задачи") }
                Text("Recovery читает состояние без повторного New Task.")
                Button(onClick=vm::createProfile,enabled=enabled && c.profiles.none { it.fields()==u.catalog?.profile }) { Text("Создать Compact Engineer") }
                c.profiles.forEach { p -> OutlinedButton(onClick={vm.select(p)},enabled=enabled && c.active()!=p) { Text("Выбрать ${p.name}") } }
              }
            }
            u.catalog?.working?.forEach { (key,value) -> item {
              OutlinedButton(onClick={vm.write(key,value)},enabled=enabled && memory!=null && memory.working[key]!=value) { Text("Сохранить $key = $value") }
            } }
            item {
              OutlinedButton(onClick={vm.lifecycle("clear-long-term")},enabled=enabled && memory!=null) { Text("Очистить Long-term") }
              Text("Live: execution Send → Pause → New Conversation → статус → New Conversation → Resume → Продолжим. Три Send, профиль неизменен.")
              TextButton(onClick={vm.message(u.catalog?.execution_query?:"");vm.page("main")}) { Text("Подставить execution query") }
              Text("Probe: ${u.catalog?.query?:""}. Ответ не сохраняется в conversation.")
              OutlinedButton(onClick=vm::probe,enabled=enabled && c?.ready==true) { Text("Probe текущего State") }
            }
          }
          "inspector" -> {
            item { Detail("Current stored State",s?.let { pretty.encodeToString(it) }?:"unavailable") }
            item { Detail("Current Memory selection preview — не actual request",c?.preview?.let { pretty.encodeToString(it) }?:"unavailable") }
            item { Detail("Последняя explicit transition (runtime)",c?.last_transition?.let { pretty.encodeToString(it) }?:"unavailable") }
            item { Text("Последняя операция dispatch: ${u.dispatch?:"unavailable"}") }
            val o=u.latest
            if(o==null) item { Text("Actual receipt unavailable — запрос ещё не записан.") }
            else {
              item { Text("Historical attempt ${o.attempt_id}\nTask ${o.stored_state.task_id} · revision ${o.stored_state.revision}\nSession ${o.memory.session_id}",Modifier.testTag("task_historical")) }
              item { Detail("Stored / selected State at dispatch",pretty.encodeToString(o.stored_state)+"\n"+pretty.encodeToString(o.selected_state)) }
              item { Detail("Memory snapshot / selection",pretty.encodeToString(o.memory)+"\n"+pretty.encodeToString(o.selection)) }
              item { Detail("Profile snapshot / section",pretty.encodeToString(o.profile)+"\n"+o.profile_section) }
              item { Detail("Rendered State section",o.state_section) }
              item { Detail("Actual LlmClient request",pretty.encodeToString(o.request)) }
              item { Detail("Actual response · conversation_committed=${o.conversation_committed}",pretty.encodeToString(o.outcome)) }
              item { Detail("Storage",pretty.encodeToString(o.storage_checks)); Detail("Selection",pretty.encodeToString(o.selection_checks)); Detail("Assembly",pretty.encodeToString(o.assembly_checks)) }
              item {
                Text("Model adherence: ${o.model_adherence.status}\n${o.model_adherence.detail}")
                OutlinedTextField(u.note,vm::note,label={Text("Наблюдение человека (только локально)")},modifier=Modifier.fillMaxWidth())
              }
            }
          }
        }
      }
    }
  }
}
@Composable private fun Detail(title: String,value: String) {
  Text(title,style=MaterialTheme.typography.titleMedium)
  SelectionContainer { Text(value) }
}
