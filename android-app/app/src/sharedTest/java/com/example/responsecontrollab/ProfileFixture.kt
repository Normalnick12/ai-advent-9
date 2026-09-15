package com.example.responsecontrollab

import com.example.responsecontrollab.data.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.serialization.json.*
import java.util.UUID

class ProfileFixture: PersonalizationRepository {
  val owner="00000000-0000-0000-0000-000000000001"
  val memory=MemoryStateDto(owner,"00000000-0000-0000-0000-000000000002","00000000-0000-0000-0000-000000000003",0,"a".repeat(64))
  val compact=ProfileFields("Compact Engineer","ru","technical","concise",ProfileFormat("summary_bullets",3),ProfileConstraints(true,true,false))
  val mentor=ProfileFields("Mentor","ru","explanatory","detailed",ProfileFormat("teaching_sections"),ProfileConstraints(true,false,true))
  var value=PersonalizationCurrent(memory=memory,binding=ProfileBinding(owner,null,0),preparation="profiles_missing")
  var reads=0; var saves=0; var selects=0; var sends=0; var probes=0; var writes=0
  var lose=false; var failRead=false; var failedOutput=false
  var gate: CompletableDeferred<Unit>?=null
  var lastSend: ProfileSend?=null
  var lastProbe: ProfileProbe?=null
  override suspend fun current(): PersonalizationCurrent { reads++; if(failRead) error("offline"); return value }
  override suspend fun catalog()=ProfileCatalog(mapOf("A" to compact,"B" to mentor),"Seed neutral","Shared query",
    mapOf("task" to "Checkout","current_architecture" to "MVI","release_marker" to "RC-42"),mapOf("project_code" to "ORION-17","preferred_architecture" to "MVVM"))
  override suspend fun initialize(): PersonalizationCurrent { writes++; value=value.copy(memory=memory,binding=ProfileBinding(owner,null,0)); return value }
  fun record(f: ProfileFields,id: String=UUID.randomUUID().toString(),revision: Int=0)=ProfileRecord(id,owner,revision,
    f.name,f.language,f.tone,f.verbosity,f.response_format,f.constraints)
  override suspend fun create(body: ProfileCreate): ProfileSaved {
    saves++; val p=record(body.fields); value=value.copy(profiles=value.profiles+p,preparation="unselected")
    if(lose) error("lost after write")
    return ProfileSaved(value,p)
  }
  override suspend fun edit(id: String,body: ProfileEdit): ProfileSaved {
    saves++; val p=record(body.fields,id,body.expected_revision+1)
    value=value.copy(profiles=value.profiles.map { if(it.profile_id==id) p else it },comparison=value.comparison?.copy(valid=false))
    if(lose) error("lost after write")
    return ProfileSaved(value,p)
  }
  override suspend fun select(id: String,body: ProfileSelect): PersonalizationCurrent {
    selects++; gate?.await()
    value=value.copy(binding=ProfileBinding(owner,id,body.expected_binding_revision+1),preparation="ready")
    if(lose) error("lost after select")
    return value
  }
  override suspend fun mutate(body: MemoryMutationRequest): PersonalizationCurrent {
    writes++; val m=value.memory!!
    value=value.copy(memory=if(body.layer=="WORKING") m.copy(working=m.working+(body.key to body.value!!)) else m.copy(long_term=m.long_term+(body.key to body.value!!)))
    return value
  }
  override suspend fun transition(action: String,body: MemorySnapshotRequest): PersonalizationCurrent {
    writes++; value=value.copy(memory=value.memory!!.copy(snapshot_id="b".repeat(64),short_term=emptyList()),comparison=value.comparison?.copy(valid=false)); return value
  }
  private fun observation(mode: String,slot: String?=null): ProfileObservation {
    val p=value.active()!!
    val check=mapOf("checked" to ProfileCheck("pass",true))
    return ProfileObservation(UUID.randomUUID().toString(),mode,slot,value.comparison?.comparison_id,value.memory!!,p,value.binding!!,
      MemorySelection(),"instructions for ${p.tone}","profile-v1",ProfileRequestEvidence(listOf(ProfileMessage("user","Shared query")),buildJsonObject { put("instructions","instructions for ${p.tone}"); put("model","fake") }),
      "Shared query",if(failedOutput) ProfileOutcome("error",error_code="fake_failure") else ProfileOutcome("completed","## Вывод\nORION-17 RC-42 Checkout MVI"),
      mode!="probe" && !failedOutput,check,check,if(failedOutput) mapOf("format" to ProfileCheck("unavailable")) else check,check)
  }
  private fun commit(o: ProfileObservation,message: String) {
    if(!o.committed) return
    val m=value.memory!!; val h=m.short_term
    value=value.copy(memory=m.copy(short_term=h+listOf(MemoryMessageDto("user",message,h.size),MemoryMessageDto("assistant",o.outcome.reply!!,h.size+1))),comparison=value.comparison?.copy(valid=false))
  }
  override suspend fun seed(body: ProfileSnapshot): ProfileOperation {
    sends++; gate?.await(); val o=observation("seed"); commit(o,"Seed neutral"); return ProfileOperation(value,o)
  }
  override suspend fun send(body: ProfileSend): ProfileOperation {
    sends++; lastSend=body; gate?.await(); val o=observation("send"); commit(o,body.message); return ProfileOperation(value,o)
  }
  override suspend fun freeze(body: ProfileFreeze): PersonalizationCurrent {
    value=value.copy(comparison=ProfileComparison(UUID.randomUUID().toString(),value.memory!!.snapshot_id,
      mapOf("A" to value.profiles.first { it.profile_id==body.profile_a_id },"B" to value.profiles.first { it.profile_id==body.profile_b_id }),"Shared query",buildJsonObject { put("model","fake") },true))
    return value
  }
  override suspend fun probe(body: ProfileProbe): ProfileOperation {
    probes++; lastProbe=body; gate?.await(); return ProfileOperation(value,observation("probe",body.slot))
  }
  fun prepared() {
    val a=record(compact); val b=record(mentor)
    value=value.copy(memory=memory.copy(working=mapOf("task" to "Checkout","current_architecture" to "MVI"),
      short_term=listOf(MemoryMessageDto("user","Seed neutral",0),MemoryMessageDto("assistant","Принято.",1))),
      profiles=listOf(a,b),binding=ProfileBinding(owner,a.profile_id,1),preparation="ready",
      comparison=ProfileComparison(UUID.randomUUID().toString(),memory.snapshot_id,mapOf("A" to a,"B" to b),"Shared query",JsonObject(emptyMap()),true))
  }
}
