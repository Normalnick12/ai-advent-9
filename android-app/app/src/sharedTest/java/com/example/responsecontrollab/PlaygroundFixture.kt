package com.example.responsecontrollab

import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.serialization.json.*
import java.util.UUID

/** Deterministic test server stand-in. No production transition logic depends on it. */
class PlaygroundFixture(empty: Boolean = false): PlaygroundRepository {
  private fun id() = UUID.randomUUID().toString()
  private val fields = ProfileFields("Compact Engineer","ru","technical","concise",
    ProfileFormat("summary_bullets",3),ProfileConstraints(true,true,false))
  val nodes = mapOf("PLANNING_REQUIREMENTS" to "Требования", "PLANNING_APPROVAL" to "Согласование плана",
    "EXECUTION_IMPLEMENT" to "Реализация", "VALIDATION_CHECK" to "Проверка", "DONE" to "Завершено")
  val labels = mapOf("REQUIREMENTS_READY" to "Требования готовы", "PLAN_APPROVED" to "Утвердить план",
    "IMPLEMENTATION_READY" to "Реализация готова", "VALIDATION_CONFIRMED" to "Подтвердить проверку",
    "REQUIREMENTS_REVISION_REQUIRED" to "Уточнить требования", "VALIDATION_FAILED" to "Проверка не пройдена",
    "PAUSE" to "Приостановить", "RESUME" to "Возобновить")
  var value = if (empty) PlaygroundCurrent() else initial(PlaygroundConfiguration())
  var reads=0; var sends=0; var events=0; var creates=0; var completes=0; var profiles=0; var conversations=0
  var failRead=false; var lose=false; var technical=false; var violate=false; var partial=false
  var gate: CompletableDeferred<Unit>? = null
  var lastCreate: PlaygroundCreate? = null
  private fun initial(config: PlaygroundConfiguration): PlaygroundCurrent {
    val owner=id(); val task=id(); val session=id()
    val profile=ProfileRecord(id(),owner,0,if(config.profile_preset=="mentor") "Mentor" else fields.name,
      fields.language,fields.tone,fields.verbosity,fields.response_format,fields.constraints)
    val binding=ProfileBinding(owner,profile.profile_id,1)
    val memory=MemoryStateDto(owner,task,session,0,"a".repeat(64),
      working=mapOf("task" to "Checkout","current_architecture" to config.policy.required_architecture))
    return sync(PlaygroundCurrent(memory=memory,profile=profile,binding=binding,
      task_state=TaskStateView(task,"checkout-v2","PLANNING_REQUIREMENTS","ACTIVE",0,
        "planning","collect_requirements","provide_requirements",false,emptyList()),
      policy=CodingPolicyRecord(task,"checkout-coding","coding-v1","d".repeat(64),config.policy),
      setup=PlaygroundSetup("playground-setup-v1","checkout-v2",config,profile.fields(),"profiles-v1",
        owner,task,session,null,ProfileBinding(owner,null,0),"ready"),
      readiness=mapOf("memory_ready" to true,"profile_ready" to true,"state_ready" to true,"policy_ready" to true,"setup_ready" to true),
      ready=true))
  }
  private fun sync(c: PlaygroundCurrent): PlaygroundCurrent {
    val m=c.memory ?: return c; val s=c.task_state ?: return c; val p=c.profile!!; val policy=c.policy!!
    val events=if(s.is_terminal) emptyList() else if(s.status=="PAUSED") listOf("RESUME") else when(s.state_id) {
      "PLANNING_REQUIREMENTS" -> listOf("REQUIREMENTS_READY","PAUSE")
      "PLANNING_APPROVAL" -> listOf("PLAN_APPROVED","REQUIREMENTS_REVISION_REQUIRED","PAUSE")
      "EXECUTION_IMPLEMENT" -> listOf("IMPLEMENTATION_READY","PAUSE")
      else -> listOf("VALIDATION_CONFIRMED","VALIDATION_FAILED","PAUSE")
    }
    return c.copy(task_state=s.copy(allowed_events=events),can_send=c.ready && !s.is_terminal,
      reference=if(c.ready) PlaygroundReference(m.task_id,m.session_id,m.snapshot_id,s.revision,p.profile_id,p.revision,
        c.binding!!.revision,policy.policy_id,policy.definition_version,policy.snapshot_id) else null,
      stage_label=nodes[s.state_id],next_action="Обсудите задачу и выберите явное действие.",
      actions=if(c.ready) events.map { PlaygroundAction(it,labels[it]!!) } else emptyList(),
      educational_event=if(s.status!="ACTIVE") null else when(s.state_id) {
        "PLANNING_APPROVAL" -> "IMPLEMENTATION_READY"; "EXECUTION_IMPLEMENT" -> "VALIDATION_CONFIRMED"; else -> null
      })
  }
  fun node(node: String) { value=sync(value.copy(task_state=value.task_state!!.copy(state_id=node,is_terminal=node=="DONE"))) }
  override suspend fun current(): PlaygroundCurrent { reads++; check(!failRead); return value }
  override suspend fun catalog()=PlaygroundCatalog("Checkout: loading/error/success + retry","checkout-v2",
    PlaygroundConfiguration(),listOf(PlaygroundPreset("compact","Compact Engineer"),PlaygroundPreset("mentor","Mentor")),
    buildJsonObject {
      put("required_architecture",JsonArray(listOf("MVI","MVVM").map(::JsonPrimitive)))
      put("required_ui_toolkit",JsonArray(listOf("Compose","Views").map(::JsonPrimitive)))
      put("required_async_model",JsonArray(listOf("CoroutinesFlow","RxJava").map(::JsonPrimitive)))
      put("payment_confirmation_required",JsonArray(listOf(JsonPrimitive(true),JsonPrimitive(false))))
    },nodes,labels)
  override suspend fun create(body: PlaygroundCreate): PlaygroundCurrent {
    creates++; lastCreate=body; value=initial(body.configuration)
    if(partial) { value=sync(value.copy(ready=false,setup=value.setup!!.copy(status="pending"),
      readiness=value.readiness+("setup_ready" to false))); error("Partial setup") }
    return value
  }
  override suspend fun complete(body: PlaygroundComplete): PlaygroundCurrent {
    completes++; check(body.task_id==value.setup!!.task_id)
    value=sync(value.copy(ready=true,setup=value.setup!!.copy(status="ready"),readiness=value.readiness+("setup_ready" to true)))
    return value
  }
  override suspend fun profile(body: PlaygroundProfileSelection): PlaygroundCurrent {
    profiles++
    value=sync(value.copy(profile=value.profile!!.copy(name=if(body.profile_preset=="mentor") "Mentor" else "Compact Engineer"),
      binding=value.binding!!.copy(revision=value.binding!!.revision+1)))
    return value
  }
  override suspend fun conversation(body: PlaygroundReference): PlaygroundCurrent {
    conversations++
    value=sync(value.copy(memory=value.memory!!.copy(session_id=id(),short_term=emptyList())))
    return value
  }
  override suspend fun event(body: PlaygroundEvent): PlaygroundOperation {
    events++; gate?.await()
    val before=value.task_state!!
    val allowed=body.event in before.allowed_events
    val kind=if(!allowed) "rejected" else when(body.event) {
      "VALIDATION_FAILED","REQUIREMENTS_REVISION_REQUIRED" -> "recovery_applied"
      "PAUSE" -> "pause_applied"; "RESUME" -> "resume_applied"; else -> "forward_applied"
    }
    if(allowed) {
      val node=when(body.event) {
        "REQUIREMENTS_READY" -> "PLANNING_APPROVAL"; "PLAN_APPROVED","VALIDATION_FAILED" -> "EXECUTION_IMPLEMENT"
        "IMPLEMENTATION_READY" -> "VALIDATION_CHECK"; "VALIDATION_CONFIRMED" -> "DONE"
        "REQUIREMENTS_REVISION_REQUIRED" -> "PLANNING_REQUIREMENTS"; else -> before.state_id
      }
      value=sync(value.copy(task_state=before.copy(state_id=node,revision=before.revision+1,is_terminal=node=="DONE",
        status=when(body.event) { "PAUSE" -> "PAUSED"; "RESUME" -> "ACTIVE"; else -> before.status })))
    }
    val receipt=PlaygroundReceipt(id(),"lifecycle",kind,"not_required",0,task_id=body.task_id,event=body.event,
      before=before,after=value.task_state,persistence=if(allowed) "committed" else "not_attempted",
      conversation="unchanged",conversation_commit="not_applicable",
      explanation=if(kind=="recovery_applied") "Проверка не пройдена. Задача возвращена на этап реализации. Следующий шаг: исправить найденные проблемы."
        else if(!allowed) "Переход отклонён. Сначала утвердите план." else "Действие применено.")
    if(lose) error("Lost event response")
    return PlaygroundOperation(value,receipt)
  }
  override suspend fun send(body: PlaygroundSend): PlaygroundOperation {
    sends++; gate?.await()
    val before=value; val m=before.memory!!
    val reply=if(violate) "Отказ по ограничениям задачи." else "Обсудим Checkout и следующий шаг."
    val empty=buildJsonObject {}
    val r=PlaygroundReceipt(id(),"send",if(technical) "technical_error" else if(violate) "candidate_refused" else "accepted",
      "dispatched",1,session_id=m.session_id,query=body.query,
      sources=PlaygroundSources(m,before.profile!!,before.binding!!,before.task_state!!,before.policy!!,
        MemorySelection(selected_working=m.working,selected_long_term=m.long_term),emptyList()),
      coverage=buildJsonObject { put("prose_semantics","not_checked") },
      actual_request=buildJsonObject { put("config",empty); put("messages",JsonArray(emptyList())) },
      raw_candidate=if(violate) "UNTRUSTED REJECTED CODE" else "RAW CANDIDATE",candidate=empty,
      candidate_preparation="parsed",precheck_status="not_applicable",assembly_status="passed",
      turn=if(technical) InvariantTurn("error",commit_status="not_attempted",error_code="provider_error")
        else InvariantTurn("completed",if(violate) "candidate_refused" else "accepted",commit_status="committed",reply=reply),
      pair_position=if(technical) null else m.short_term.size)
    if(!technical) value=sync(value.copy(memory=m.copy(short_term=m.short_term+
      listOf(MemoryMessageDto("user",body.query,m.short_term.size),MemoryMessageDto("assistant",reply,m.short_term.size+1)),
      snapshot_id="b".repeat(64))))
    if(lose) error("Lost Send response")
    return PlaygroundOperation(value,r)
  }
}
