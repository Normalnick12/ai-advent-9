package com.example.responsecontrollab.ui.invariants

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
fun InvariantsScreen(vm: InvariantsViewModel,onBack: ()->Unit) {
  val u by vm.uiState.collectAsState()
  LaunchedEffect(Unit) { vm.load() }
  BackHandler(u.page!="main") { vm.page("main") }
  val c=u.current; val m=c?.memory; val s=c?.task_state
  val enabled=u.loaded && !u.busy && !u.recovery && c?.busy!=true
  val pages=rememberSaveableStateHolder()
  Scaffold(topBar={ LearningDayTopBar(LearningDay.INVARIANTS) { if(u.page=="main") onBack() else vm.page("main") } }) { padding ->
    pages.SaveableStateProvider(u.page) {
      LazyColumn(state=rememberLazyListState(),modifier=Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
        .imePadding().testTag("invariants_scroll"),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item {
          if(u.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
          u.error?.let { Text(it,color=MaterialTheme.colorScheme.error,modifier=Modifier.testTag("invariants_error")) }
          if(u.recovery) Text("Нужно перечитать состояние. Повтора операции не будет.")
          TextButton(onClick=vm::refresh,enabled=!u.busy) { Text("Прочитать backend") }
          FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            for((page,label) in listOf("main" to "Задача","setup" to "Подготовка","inspector" to "Inspector"))
              FilterChip(selected=u.page==page,onClick={vm.page(page)},label={Text(label)},modifier=Modifier.testTag("invariants_page_$page"))
          }
        }
        when(u.page) {
          "main" -> {
            item {
              Text(m?.working?.get("task")?:"Checkout не подготовлен",style=MaterialTheme.typography.titleLarge)
              Text("Working: ${m?.working?.filterKeys { it!="task" }?:emptyMap<String,String>()}")
              Text("Long-term: ${m?.long_term?:emptyMap<String,String>()}")
              Text("Profile: ${c?.profile?.name?:"не выбран"}")
              Text("State: ${s?.state_id?:"отсутствует"} · ${s?.status?:"—"}")
              Text("Generation calls: ${c?.generation_calls?:0}")
              if(c?.can_propose!=true) Text("Подготовьте источники и переведите State в ACTIVE execution.",Modifier.testTag("invariants_not_ready"))
              c?.source_error?.let { Text("Ошибка источника: $it",color=MaterialTheme.colorScheme.error) }
            }
            item {
              Card(Modifier.fillMaxWidth().testTag("invariants_card")) { Column(Modifier.padding(16.dp)) {
                Text("Инварианты задачи",style=MaterialTheme.typography.titleMedium)
                val p=c?.policy
                if(p==null) Text("Policy отсутствует") else {
                  Text("${p.values.required_architecture} · ${p.values.required_ui_toolkit} · ${p.values.required_async_model}")
                  Text("Подтверждение оплаты: ${p.values.payment_confirmation_required}")
                  Text("${p.policy_id} / ${p.definition_version} · task ${p.task_id.take(8)}")
                }
                Text("Подсказка модели помогает; принятие проверяет deterministic validator.")
              } }
            }
            u.catalog?.actions?.forEach { a -> item {
              Text(a.text)
              Button(onClick={vm.propose(a.action_id)},enabled=enabled && c?.can_propose==true,
                modifier=Modifier.testTag("invariants_${a.action_id}")) {
                Text(if(a.action_id=="compatible-retry") "Предложить retry" else "Проверить конфликт")
              }
            } }
            u.latest?.let { o -> item {
              Text("Последняя попытка · ${o.turn.decision?:o.turn.status}")
              Text("Provider: ${o.provider_dispatch} · calls=${o.generation_calls}\nCommit: ${o.turn.commit_status}",Modifier.testTag("invariants_outcome"))
              Text("Session ${o.memory.session_id.take(8)} · ${if(o.memory.session_id==m?.session_id) "текущая" else "предыдущая conversation"}")
              if(o.turn.status=="completed") SelectionContainer { Text(o.turn.reply?:"",Modifier.testTag("invariants_reply")) }
              else Text("Технический исход: ${o.turn.error_code}. Семантический отказ не создан.")
              TextButton(onClick={vm.page("inspector")}) { Text("Открыть receipt") }
            } }
            if(m!=null) item {
              Text("Session ${m.session_id.take(8)} · ${m.short_term.size/2} turns")
              FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick={vm.lifecycle("new-conversation")},enabled=enabled,modifier=Modifier.testTag("invariants_new_conversation")) { Text("New Conversation") }
                OutlinedButton(onClick={vm.lifecycle("new-task")},enabled=enabled) { Text("New Task") }
              }
              Text("New Conversation сохраняет task policy. New Task требует новой подготовки.")
            }
          }
          "setup" -> {
            item {
              Text("Явная подготовка · без вызова модели",style=MaterialTheme.typography.titleLarge)
              u.catalog?.let { fixture ->
                Text("Будет сохранено: ${fixture.working}")
                Text("Profile: ${fixture.profile.name} · ${fixture.profile.language} · ${fixture.profile.tone} · ${fixture.profile.verbosity}")
                Text("Policy: ${fixture.policy.required_architecture}, ${fixture.policy.required_ui_toolkit}, ${fixture.policy.required_async_model}, payment confirmation=${fixture.policy.payment_confirmation_required}")
              }
              if(m==null) Button(onClick=vm::initialize,enabled=enabled,modifier=Modifier.testTag("invariants_initialize")) { Text("Создать задачу Day 14") }
              else {
                Text("Memory: ${c.readiness.memory_ready} · Profile: ${c.readiness.profile_ready}\nState: ${c.readiness.state_ready} · Policy: ${c.readiness.policy_ready}\nConsistency: ${c.readiness.consistent}")
                Button(onClick=vm::setup,enabled=enabled && !c.ready,modifier=Modifier.testTag("invariants_setup")) { Text("Дополнить подготовку") }
                Text("Заполняются только отсутствующие компоненты на текущих IDs. Существующие значения не заменяются.")
                Text("State: ${s?.state_id?:"отсутствует"} · ${s?.status?:"—"}")
                FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                  s?.allowed_events?.forEach { event ->
                    Button(onClick={vm.event(event)},enabled=enabled && c.ready,modifier=Modifier.testTag("invariants_event_$event")) { Text(event.replace('_',' ')) }
                  }
                }
                Text("Для опыта: REQUIREMENTS READY → PLAN APPROVED. Ответ или отказ не меняет State.")
              }
            }
          }
          "inspector" -> {
            item { Detail("Current sources — не historical receipt",c?.let { pretty.encodeToString(it) }?:"unavailable") }
            val o=u.latest
            if(o==null) item { Text("Receipt unavailable — попытки ещё не было.") }
            else {
              item { Text("Historical attempt ${o.attempt_id}\nTask ${o.memory.task_id}\nSession ${o.memory.session_id}",Modifier.testTag("invariants_historical")) }
              item { Detail("Attempt sources / selection",pretty.encodeToString(o.memory)+"\n"+pretty.encodeToString(o.policy)+"\n"+pretty.encodeToString(o.profile)+"\n"+pretty.encodeToString(o.binding)+"\n"+pretty.encodeToString(o.state)+"\n"+o.selection) }
              item { Detail("Trusted invariant guidance / rules",o.invariant_section+"\n"+o.rules); Detail("Request / controlled intent",o.query+"\n"+o.intent) }
              item { Detail("Actual provider input · ${o.provider_dispatch} · ${o.generation_calls} calls",o.actual_request?.let { pretty.encodeToString(it) }?:"not dispatched — actual request отсутствует") }
              item { Detail("Candidate preparation: ${o.candidate_preparation}",o.candidate?.let { pretty.encodeToString(it) }?:"candidate отсутствует") }
              item { Detail(if(o.turn.decision=="candidate_refused") "Raw candidate — отклонён, не сохранён в conversation (диагностика)" else "Raw candidate — диагностические данные, не принятый ответ",o.raw_candidate?:"отсутствует") }
              item { Detail("Precheck / validation / decision / commit",pretty.encodeToString(o.turn)) }
              item { Detail("Provider outcome / usage",o.provider_outcome?.let { pretty.encodeToString(it) }?:"not dispatched") }
              item { Detail("Storage / selection / assembly",o.storage_checks.toString()+"\n"+o.selection_checks+"\n"+o.assembly_checks); Text("Adherence: ${o.model_adherence}. Гарантия ограничена typed decisions; произвольный код не проверяется.") }
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
