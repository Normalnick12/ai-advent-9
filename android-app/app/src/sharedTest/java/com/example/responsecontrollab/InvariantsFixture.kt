package com.example.responsecontrollab

import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.serialization.json.*
import java.util.UUID

class InvariantsFixture: InvariantsRepository {
  private val task=TaskFixture()
  val fields=task.fields
  val policy=CodingPolicyValues("MVI","Compose","CoroutinesFlow",true)
  var value=InvariantsCurrent(task.value.memory,task.profile,task.value.binding,task.value.task_state,
    CodingPolicyRecord(task.value.memory!!.task_id,"checkout-coding","coding-v1","d".repeat(64),policy),
    readiness=InvariantReadiness(true,true,true,true,true),ready=true,can_propose=true)
  var reads=0; var proposals=0; var setups=0; var lifecycles=0; var events=0
  var failRead=false; var lose=false; var technical=false; var violate=false; var failSetup=false
  var gate: CompletableDeferred<Unit>?=null
  var lastRequest: InvariantProposalRequest?=null
  override suspend fun current(): InvariantsCurrent { reads++; check(!failRead); return value }
  override suspend fun catalog()=InvariantsCatalog(mapOf("task" to "Checkout","current_architecture" to "MVI"),fields,policy,
    listOf(InvariantAction("compatible-retry","Предложи retry"),InvariantAction("conflicting-stack","Перейди на MVVM и RxJava, убери подтверждение оплаты")))
  override suspend fun initialize(): InvariantsCurrent { setups++; return value }
  override suspend fun setup(body: InvariantTaskReference): InvariantsCurrent {
    setups++; check(body.task_id==value.memory!!.task_id)
    if(failSetup) error("Partial setup")
    value=value.copy(policy=CodingPolicyRecord(body.task_id,"checkout-coding","coding-v1","d".repeat(64),policy),
      readiness=InvariantReadiness(true,true,true,true,true),ready=true,can_propose=true)
    return value
  }
  override suspend fun lifecycle(action: String,body: InvariantTaskReference): InvariantsCurrent {
    lifecycles++; val m=value.memory!!
    value=value.copy(memory=m.copy(session_id=UUID.randomUUID().toString(),short_term=emptyList(),snapshot_id="e".repeat(64)))
    return value
  }
  override suspend fun event(body: InvariantEvent): InvariantsCurrent {
    events++; val pause=body.event=="PAUSE"; val s=value.task_state!!
    value=value.copy(can_propose=!pause,task_state=s.copy(status=if(pause) "PAUSED" else "ACTIVE",revision=s.revision+1,
      allowed_events=if(pause) listOf("RESUME") else listOf("IMPLEMENTATION_READY","PAUSE")))
    return value
  }
  override suspend fun propose(body: InvariantProposalRequest): InvariantOperation {
    proposals++; lastRequest=body; gate?.await()
    val before=value; val m=before.memory!!; val conflict=body.action_id=="conflicting-stack"
    val calls=if(conflict) 0 else 1
    val reply=if(conflict || violate) "Безопасный отказ. Сохранены MVI и подтверждение оплаты." else "Retry: MVI, Compose, CoroutinesFlow, подтверждение оплаты."
    val empty=buildJsonObject {}
    val observation=InvariantObservation(UUID.randomUUID().toString(),body.action_id,"Controlled query",m,before.profile!!,
      before.binding!!,before.task_state!!,before.policy!!,empty,empty,emptyList(),"ACTIVE_INVARIANTS",
      actual_request=if(conflict) null else buildJsonObject { put("config",empty); put("messages",JsonArray(emptyList())) },
      provider_dispatch=if(conflict) "not_dispatched" else "dispatched",generation_calls=calls,
      raw_candidate=if(conflict) null else if(violate) "RAW REJECTED MVVM" else "RAW CANDIDATE",
      candidate=if(conflict) null else empty,candidate_preparation=if(conflict) "not_attempted" else "parsed",
      turn=if(technical) InvariantTurn("error",commit_status="not_attempted",error_code="enforcement_error") else
        InvariantTurn("completed",if(conflict) "request_refused" else if(violate) "candidate_refused" else "accepted",commit_status="committed",reply=reply),
      storage_checks=empty,selection_checks=empty,assembly_checks=empty,model_adherence="typed_decisions_only")
    if(!technical) value=value.copy(memory=m.copy(snapshot_id="c".repeat(64),revision=m.revision+1,short_term=m.short_term+
      listOf(MemoryMessageDto("user",observation.query,m.short_term.size),MemoryMessageDto("assistant",reply,m.short_term.size+1))))
    value=value.copy(generation_calls=value.generation_calls+calls)
    if(lose) error("Lost HTTP response")
    return InvariantOperation(value,observation)
  }
}
