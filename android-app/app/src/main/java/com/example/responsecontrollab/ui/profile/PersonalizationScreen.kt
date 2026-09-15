package com.example.responsecontrollab.ui.profile

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.ui.semantics.Role
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.responsecontrollab.data.*
import com.example.responsecontrollab.ui.LearningDay
import com.example.responsecontrollab.ui.LearningDayTopBar
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val pretty=Json { prettyPrint=true; encodeDefaults=true }

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PersonalizationScreen(vm: PersonalizationViewModel,onBack: ()->Unit) {
  val u by vm.uiState.collectAsState()
  LaunchedEffect(Unit) { vm.load() }
  BackHandler(u.page!="main") { vm.page("main") }
  val enabled=!u.busy && !u.recovery && u.current?.busy!=true
  val pages=rememberSaveableStateHolder()
  Scaffold(topBar={ LearningDayTopBar(LearningDay.PERSONALIZATION) { if(u.page=="main") onBack() else vm.page("main") } }) { padding ->
    pages.SaveableStateProvider(if(u.page=="editor") "editor-${u.editorKey}" else u.page) {
      LazyColumn(state=rememberLazyListState(),modifier=Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
        .imePadding().testTag("profile_scroll"),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item {
          if(u.page!="main") TextButton(onClick={vm.page("main")}) { Text("К персонализации") }
          if(u.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
          u.error?.let { Text(it,color=MaterialTheme.colorScheme.error) }
          TextButton(onClick=vm::refresh,enabled=!u.busy) { Text("Прочитать backend") }
        }
        when(u.page) {
          "editor" -> {
            item { Text(if(u.draft.id==null) "Создать профиль" else "Редактировать профиль · revision ${u.draft.revision}",style=MaterialTheme.typography.titleLarge) }
            item { OutlinedTextField(u.draft.name,{vm.draft(u.draft.copy(name=it))},label={Text("Название — только метаданные")},enabled=enabled,modifier=Modifier.fillMaxWidth().testTag("profile_name")) }
            item { Choices("Язык",listOf("ru" to "Русский","en" to "English"),u.draft.language,enabled) { vm.draft(u.draft.copy(language=it)) } }
            item { Choices("Тон",listOf("technical" to "Технический","explanatory" to "Объясняющий"),u.draft.tone,enabled) { vm.draft(u.draft.copy(tone=it)) } }
            item { Choices("Подробность",listOf("concise" to "Кратко","detailed" to "Подробно"),u.draft.verbosity,enabled) { vm.draft(u.draft.copy(verbosity=it)) } }
            item { Choices("Формат",listOf("summary_bullets" to "Вывод и список","teaching_sections" to "Четыре раздела"),u.draft.format,enabled) { vm.draft(u.draft.copy(format=it)) } }
            if(u.draft.format=="summary_bullets") item { Choices("Максимум пунктов",(1..5).map { it.toString() to it.toString() },u.draft.maxBullets.toString(),enabled) { vm.draft(u.draft.copy(maxBullets=it.toInt())) } }
            item { Toggle("Без emoji",u.draft.noEmoji,enabled) { vm.draft(u.draft.copy(noEmoji=it)) } }
            item { Toggle("Пропускать базовые Android/Kotlin понятия",u.draft.skipBasics,enabled) { vm.draft(u.draft.copy(skipBasics=it)) } }
            item { Toggle("Объяснять новые специальные термины",u.draft.explainTerms,enabled) { vm.draft(u.draft.copy(explainTerms=it)) } }
            item { Text("Оба ограничения объяснений совместимы. Название не задаёт поведение модели."); Button(onClick=vm::save,enabled=enabled && u.draft.name.trim().length in 1..80) { Text("Сохранить профиль") } }
          }
          "inspector" -> {
            val o=u.inspected
            if(o!=null) {
              item { Text("Фактический запрос · ${o.mode}",style=MaterialTheme.typography.titleLarge)
                Text(if(u.current?.memory?.snapshot_id==o.memory.snapshot_id && u.current?.active()==o.profile) "Снимок соответствует текущему состоянию" else "Предыдущий снимок",Modifier.testTag("profile_snapshot_label"))
                Text("Attempt ${o.attempt_id}\nProfile ${o.profile.profile_id} · revision ${o.profile.revision}\nBinding revision ${o.binding.revision}\nSnapshot ${o.memory.snapshot_id}") }
              item { Selectable("Typed Profile",pretty.encodeToString(o.profile)) }
              item { Selectable("Profile instructions · ${o.template_version}",o.profile_instructions) }
              item { Selectable("Memory snapshot",pretty.encodeToString(o.memory)) }
              item { Selectable("Выбранная память",pretty.encodeToString(o.selection)) }
              item { Selectable("Actual LlmClient arguments",pretty.encodeToString(o.request),"profile_actual_request") }
              item { Response(o); Checks("Selection",o.selection_checks); Checks("Assembly",o.assembly_checks) }
              item { Checks("Deterministic adherence",o.adherence_checks); Checks("Memory markers · только literal mentions",o.marker_checks) }
              item { Text("Human observations: язык, тон, подробность, объяснение терминов, полезность и корректность MVI оцениваются отдельно.")
                OutlinedTextField(u.notes[o.attempt_id]?:"",{vm.note(o.attempt_id,it)},label={Text("Мои наблюдения — без score")},modifier=Modifier.fillMaxWidth().testTag("profile_notes")) }
            } else item { Text("Actual receipt отсутствует. Preview не является отправленным запросом.") }
          }
          else -> {
            item {
              Text("Memory — что агент знает. Profile — как отвечает.")
              Text("Active Profile: ${u.current?.active()?.name?:"не выбран"}",Modifier.testTag("active_profile"))
              Text("Generation calls: ${u.current?.generation_calls?:0}")
              if(u.current?.memory==null) Button(onClick=vm::initialize,enabled=enabled) { Text("Создать память Day 12") }
              else Button(onClick={vm.edit()},enabled=enabled) { Text("Новый профиль") }
            }
            if(u.current?.memory!=null) item {
              Text("Шаблоны открывают обычный редактируемый профиль:")
              u.catalog?.profiles?.forEach { (slot,fields) ->
                OutlinedButton(onClick={vm.edit(template=fields)},enabled=enabled) { Text("Создать из $slot · ${fields.name}") }
              }
            }
            items(u.current?.profiles?:emptyList(),key={it.profile_id}) { p ->
              Card(Modifier.fillMaxWidth().testTag("profile_${p.profile_id}")) {
                Column(Modifier.padding(12.dp)) {
                  Text("${p.name} · ${p.profile_id.take(8)} · r${p.revision}",style=MaterialTheme.typography.titleMedium)
                  Text("${p.language} · ${p.tone} · ${p.verbosity} · ${p.response_format.kind}")
                  FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    Button(onClick={vm.select(p)},enabled=enabled && u.current?.active()!=p) { Text("Выбрать") }
                    OutlinedButton(onClick={vm.edit(p)},enabled=enabled) { Text("Изменить") }
                    for(slot in listOf("A","B")) FilterChip(selected=u.slots[slot]==p.profile_id,onClick={vm.slot(slot,p)},enabled=enabled,label={Text("Слот $slot")})
                  }
                }
              }
            }
            u.current?.memory?.let { memory ->
              item {
                Text("Память",style=MaterialTheme.typography.titleLarge)
                Text("Owner ${memory.memory_owner_id.take(8)} · Task ${memory.task_id.take(8)}\nSession ${memory.session_id.take(8)} · Snapshot ${memory.snapshot_id.take(12)}")
                Text("Working: ${memory.working}\nLong-term: ${memory.long_term}\nShort-term: ${memory.short_term.size/2} turns")
                Text("Switch не меняет conversation, task или Memory.")
                FlowRow {
                  OutlinedButton(onClick={vm.transition("new-conversation")},enabled=enabled) { Text("Новый разговор") }
                  OutlinedButton(onClick={vm.transition("new-task")},enabled=enabled) { Text("Новая задача") }
                  OutlinedButton(onClick={vm.transition("clear-long-term")},enabled=enabled) { Text("Очистить Long-term") }
                }
              }
              item {
                Text("Подготовка controlled A/B",style=MaterialTheme.typography.titleLarge)
                Text("1. Выберите Compact Engineer. Отправьте seed в пустую память. Прочитайте реальный ответ; оцените нейтральность перед Freeze.")
                Button(onClick=vm::seed,enabled=enabled && u.current?.active()!=null && memory.short_term.isEmpty() && memory.working.isEmpty() && memory.long_term.isEmpty()) { Text("Отправить seed") }
                memory.short_term.take(2).forEach { Text("${it.role}: ${it.content}") }
                Toggle("Seed прочитан: стиль достаточно нейтрален",u.seedReviewed,enabled && memory.short_term.size==2,vm::seedReviewed)
                Text("2. Сохраните факты. Working MVI имеет приоритет над Long-term MVVM.")
              }
              u.catalog?.let { catalog ->
                for((layer,values) in listOf("LONG_TERM" to catalog.long_term,"WORKING" to catalog.working)) {
                  items(values.entries.toList(),key={"$layer-${it.key}"}) { (key,value) ->
                    val stored=if(layer=="WORKING") memory.working[key] else memory.long_term[key]
                    OutlinedButton(onClick={vm.write(layer,key,value)},enabled=enabled && stored!=value) { Text("$layer · $key = $value") }
                  }
                }
              }
              item {
                Text("3. Назначьте профили слотам A/B. Freeze фиксирует revisions и один общий transcript.")
                Button(onClick=vm::freeze,enabled=enabled && u.seedReviewed && u.slots.keys.containsAll(listOf("A","B")) && u.current?.active()!=null) { Text("Freeze") }
                u.current?.comparison?.let { Text("Comparison ${it.comparison_id}\n${if(it.valid) "Снимок актуален" else "Снимок устарел — подготовьте новый"}\n${it.query}") }
              }
              for(slot in listOf("A","B")) item {
                val frozen=u.current?.comparison
                val result=u.results[slot]
                Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(12.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                  Text("Profile $slot",style=MaterialTheme.typography.titleMedium)
                  Text("Для probe явно выберите профиль ${frozen?.profiles?.get(slot)?.name?:slot} через selector.")
                  Button(onClick={vm.probe(slot)},enabled=enabled && frozen?.valid==true && u.current?.active()==frozen.profiles[slot]) { Text("Probe $slot") }
                  if(result!=null) {
                    Text("Snapshot ${result.memory.snapshot_id.take(12)} · r${result.profile.revision} · ${if(result.comparison_id==frozen?.comparison_id) "текущий comparison" else "предыдущий comparison"}")
                    Response(result)
                    Checks("Selection",result.selection_checks); Checks("Assembly",result.assembly_checks)
                    Checks("Deterministic adherence",result.adherence_checks)
                    OutlinedButton(onClick={vm.inspect(result)}) { Text("Inspector $slot") }
                  } else Text("Нет измерения")
                } }
              }
              item {
                Text("Обычный Send",style=MaterialTheme.typography.titleLarge)
                Text("Использует current Profile и Memory автоматически, сохраняет completed pair. После Send frozen comparison устаревает.")
                OutlinedTextField(u.message,vm::message,label={Text("Сообщение")},enabled=enabled,modifier=Modifier.fillMaxWidth().testTag("profile_message"))
                Button(onClick=vm::send,enabled=enabled && u.current?.active()!=null && u.message.isNotBlank()) { Text("Отправить") }
              }
              u.latest?.let { o -> item { Text("Последний actual result · ${o.mode}"); Response(o); OutlinedButton(onClick={vm.inspect(o)}) { Text("Inspector последнего запроса") } } }
              items(memory.short_term.drop(2),key={"turn-${it.position}"}) { Text("${it.role}: ${it.content}") }
            }
          }
        }
      }
    }
  }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable private fun Choices(title: String,options: List<Pair<String,String>>,value: String,enabled: Boolean,onChange: (String)->Unit) {
  Column { Text(title,style=MaterialTheme.typography.titleMedium)
    FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) { options.forEach { (key,label) -> FilterChip(selected=key==value,onClick={onChange(key)},enabled=enabled,label={Text(label)}) } }
  }
}
@Composable private fun Toggle(label: String,value: Boolean,enabled: Boolean,onChange: (Boolean)->Unit) {
  Row(Modifier.fillMaxWidth().toggleable(value=value,enabled=enabled,role=Role.Checkbox,onValueChange=onChange)) {
    Checkbox(value,null,enabled=enabled); Text(label,Modifier.padding(top=12.dp))
  }
}
@Composable private fun Selectable(title: String,text: String,tag: String="profile_detail") {
  Text(title,style=MaterialTheme.typography.titleMedium)
  SelectionContainer { Text(text,Modifier.testTag(tag)) }
}
@Composable private fun Response(o: ProfileObservation) {
  Text("${o.outcome.status} · committed=${o.committed}")
  o.outcome.reply?.let { SelectionContainer { Text(it) } }
  if(o.outcome.status!="completed") Text("Output adherence: unavailable · ${o.outcome.error_code?:o.outcome.incomplete_reason?:o.outcome.status}")
}
@Composable private fun Checks(title: String,checks: Map<String,ProfileCheck>) {
  Text(title,style=MaterialTheme.typography.titleSmall)
  checks.forEach { (key,c) -> Text("$key: ${c.status}${if(c.detail.isNotEmpty()) " · ${c.detail}" else ""}") }
}
