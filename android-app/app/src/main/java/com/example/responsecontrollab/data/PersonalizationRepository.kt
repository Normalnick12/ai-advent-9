package com.example.responsecontrollab.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import retrofit2.http.*
import java.util.UUID

@Serializable data class ProfileFormat(val kind: String, val max_bullets: Int? = null) {
  init { require(if(kind=="summary_bullets") max_bullets in 1..5 else kind=="teaching_sections" && max_bullets==null) }
}
@Serializable data class ProfileConstraints(val no_emoji: Boolean, val skip_basic_explanations: Boolean, val explain_unfamiliar_terms: Boolean)
@Serializable data class ProfileFields(val name: String, val language: String, val tone: String, val verbosity: String,
  val response_format: ProfileFormat, val constraints: ProfileConstraints) {
  init {
    require(name.trim().length in 1..80 && language in listOf("ru","en"))
    require(tone in listOf("technical","explanatory") && verbosity in listOf("concise","detailed"))
  }
}
@Serializable data class ProfileRecord(val profile_id: String, val owner_id: String, val revision: Int,
  val name: String, val language: String, val tone: String, val verbosity: String,
  val response_format: ProfileFormat, val constraints: ProfileConstraints) {
  fun fields() = ProfileFields(name,language,tone,verbosity,response_format,constraints)
}
@Serializable data class ProfileBinding(val owner_id: String, val active_profile_id: String? = null, val revision: Int)
@Serializable data class ProfileComparison(val comparison_id: String, val snapshot_id: String,
  val profiles: Map<String,ProfileRecord>, val query: String, val settings: JsonObject, val valid: Boolean)
@Serializable data class PersonalizationCurrent(val memory: MemoryStateDto? = null, val profiles: List<ProfileRecord> = emptyList(),
  val binding: ProfileBinding? = null, val preview: MemorySelection? = null, val busy: Boolean = false,
  val comparison: ProfileComparison? = null, val generation_calls: Int = 0, val preparation: String = "not_initialized") {
  fun active() = profiles.find { it.profile_id == binding?.active_profile_id }
  fun snapshot(): ProfileSnapshot = ProfileSnapshot(requireNotNull(memory).snapshot_id,
    requireNotNull(active()).profile_id,requireNotNull(active()).revision,requireNotNull(binding).revision)
}
@Serializable data class ProfileCatalog(val profiles: Map<String,ProfileFields>, val seed: String, val query: String,
  val working: Map<String,String>, val long_term: Map<String,String>)
@Serializable data class ProfileCheck(val status: String, val correct: Boolean? = null, val detail: String = "")
@Serializable data class ProfileOutcome(val status: String, val reply: String? = null, val error_code: String? = null,
  val incomplete_reason: String? = null)
@Serializable data class ProfileMessage(val role: String, val content: String)
@Serializable data class ProfileRequestEvidence(val messages: List<ProfileMessage>, val config: JsonObject)
@Serializable data class ProfileObservation(val attempt_id: String, val mode: String, val slot: String? = null,
  val comparison_id: String? = null, val memory: MemoryStateDto, val profile: ProfileRecord, val binding: ProfileBinding,
  val selection: MemorySelection, val profile_instructions: String, val template_version: String,
  val request: ProfileRequestEvidence, val query: String, val outcome: ProfileOutcome, val committed: Boolean,
  val selection_checks: Map<String,ProfileCheck>, val assembly_checks: Map<String,ProfileCheck>,
  val adherence_checks: Map<String,ProfileCheck>, val marker_checks: Map<String,ProfileCheck>)
@Serializable data class ProfileOperation(val current: PersonalizationCurrent, val observation: ProfileObservation)
@Serializable data class ProfileSaved(val current: PersonalizationCurrent, val profile: ProfileRecord)
@Serializable data class ProfileCreate(val owner_id: String, val fields: ProfileFields)
@Serializable data class ProfileEdit(val owner_id: String, val fields: ProfileFields, val expected_revision: Int)
@Serializable data class ProfileSelect(val owner_id: String, val expected_profile_revision: Int, val expected_binding_revision: Int)
@Serializable data class ProfileSnapshot(val snapshot_id: String, val profile_id: String, val profile_revision: Int, val binding_revision: Int)
@Serializable data class ProfileSend(val snapshot_id: String, val profile_id: String, val profile_revision: Int,
  val binding_revision: Int, val message: String) {
  constructor(s: ProfileSnapshot,message: String): this(s.snapshot_id,s.profile_id,s.profile_revision,s.binding_revision,message)
}
@Serializable data class ProfileFreeze(val snapshot_id: String, val profile_id: String, val profile_revision: Int,
  val binding_revision: Int, val profile_a_id: String, val profile_a_revision: Int, val profile_b_id: String, val profile_b_revision: Int) {
  constructor(s: ProfileSnapshot,a: ProfileRecord,b: ProfileRecord): this(s.snapshot_id,s.profile_id,s.profile_revision,s.binding_revision,
    a.profile_id,a.revision,b.profile_id,b.revision)
}
@Serializable data class ProfileProbe(val snapshot_id: String, val profile_id: String, val profile_revision: Int,
  val binding_revision: Int, val comparison_id: String, val slot: String) {
  constructor(s: ProfileSnapshot,id: String,slot: String): this(s.snapshot_id,s.profile_id,s.profile_revision,s.binding_revision,id,slot)
}

interface PersonalizationApi {
  @GET("api/v1/profile-personalization/current") suspend fun current(): PersonalizationCurrent
  @GET("api/v1/profile-personalization/scenario") suspend fun catalog(): ProfileCatalog
  @POST("api/v1/profile-personalization/initialize") suspend fun initialize(@Body body: Map<String,String>): PersonalizationCurrent
  @POST("api/v1/profile-personalization/profiles") suspend fun create(@Body body: ProfileCreate): ProfileSaved
  @PUT("api/v1/profile-personalization/profiles/{id}") suspend fun edit(@Path("id") id: String,@Body body: ProfileEdit): ProfileSaved
  @POST("api/v1/profile-personalization/profiles/{id}/select") suspend fun select(@Path("id") id: String,@Body body: ProfileSelect): PersonalizationCurrent
  @POST("api/v1/profile-personalization/memory") suspend fun mutate(@Body body: MemoryMutationRequest): PersonalizationCurrent
  @POST("api/v1/profile-personalization/lifecycle/{action}") suspend fun transition(@Path("action") action: String,@Body body: MemorySnapshotRequest): PersonalizationCurrent
  @POST("api/v1/profile-personalization/seed") suspend fun seed(@Body body: ProfileSnapshot): ProfileOperation
  @POST("api/v1/profile-personalization/messages") suspend fun send(@Body body: ProfileSend): ProfileOperation
  @POST("api/v1/profile-personalization/freeze") suspend fun freeze(@Body body: ProfileFreeze): PersonalizationCurrent
  @POST("api/v1/profile-personalization/probe") suspend fun probe(@Body body: ProfileProbe): ProfileOperation
}

interface PersonalizationRepository {
  suspend fun current(): PersonalizationCurrent
  suspend fun catalog(): ProfileCatalog
  suspend fun initialize(): PersonalizationCurrent
  suspend fun create(body: ProfileCreate): ProfileSaved
  suspend fun edit(id: String,body: ProfileEdit): ProfileSaved
  suspend fun select(id: String,body: ProfileSelect): PersonalizationCurrent
  suspend fun mutate(body: MemoryMutationRequest): PersonalizationCurrent
  suspend fun transition(action: String,body: MemorySnapshotRequest): PersonalizationCurrent
  suspend fun seed(body: ProfileSnapshot): ProfileOperation
  suspend fun send(body: ProfileSend): ProfileOperation
  suspend fun freeze(body: ProfileFreeze): PersonalizationCurrent
  suspend fun probe(body: ProfileProbe): ProfileOperation
}

class DefaultPersonalizationRepository(private val api: PersonalizationApi): PersonalizationRepository {
  private fun uuid(id: String) { require(UUID.fromString(id).toString()==id) }
  private fun ProfileRecord.valid(owner: String) { uuid(profile_id); require(owner_id==owner && revision>=0); fields() }
  private fun PersonalizationCurrent.valid() = apply {
    memory?.let { m ->
      listOf(m.memory_owner_id,m.task_id,m.session_id).forEach(::uuid)
      require(m.snapshot_id.matches(Regex("[a-f0-9]{64}")) && m.revision>=0 && m.short_term.size%2==0)
      m.short_term.forEachIndexed { i,v -> require(v.position==i && v.role==if(i%2==0) "user" else "assistant") }
      profiles.forEach { it.valid(m.memory_owner_id) }
      require(profiles.map { it.profile_id }.distinct().size==profiles.size)
      require(binding?.owner_id==m.memory_owner_id && binding.revision>=0)
      require(if(binding.active_profile_id==null) binding.revision==0 else active()!=null && binding.revision>0)
    } ?: require(profiles.isEmpty() && binding==null)
  }
  private fun ProfileSaved.valid() = apply { current.valid(); require(profile in current.profiles) }
  private fun ProfileOperation.valid(s: ProfileSnapshot,probe: Boolean) = apply {
    current.valid()
    val o=observation
    require(o.memory.snapshot_id==s.snapshot_id && o.profile.profile_id==s.profile_id && o.profile.revision==s.profile_revision)
    o.profile.valid(o.memory.memory_owner_id)
    require(o.binding.owner_id==o.profile.owner_id && o.binding.active_profile_id==s.profile_id && o.binding.revision==s.binding_revision)
    require(current.memory?.memory_owner_id==o.memory.memory_owner_id)
    if(probe) require(!o.committed && current.memory==o.memory)
  }
  override suspend fun current()=api.current().valid()
  override suspend fun catalog()=api.catalog()
  override suspend fun initialize()=api.initialize(emptyMap()).valid()
  override suspend fun create(body: ProfileCreate)=api.create(body).valid()
  override suspend fun edit(id: String,body: ProfileEdit)=api.edit(id,body).valid()
  override suspend fun select(id: String,body: ProfileSelect)=api.select(id,body).valid()
  override suspend fun mutate(body: MemoryMutationRequest)=api.mutate(body).valid()
  override suspend fun transition(action: String,body: MemorySnapshotRequest)=api.transition(action,body).valid()
  override suspend fun seed(body: ProfileSnapshot)=api.seed(body).valid(body,false)
  override suspend fun send(body: ProfileSend)=api.send(body).valid(ProfileSnapshot(body.snapshot_id,body.profile_id,body.profile_revision,body.binding_revision),false)
  override suspend fun freeze(body: ProfileFreeze)=api.freeze(body).valid()
  override suspend fun probe(body: ProfileProbe)=api.probe(body).valid(ProfileSnapshot(body.snapshot_id,body.profile_id,body.profile_revision,body.binding_revision),true)
}
