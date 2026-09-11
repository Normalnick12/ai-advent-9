package com.example.responsecontrollab.data

import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

private const val EMULATOR_BACKEND_URL = "http://10.0.2.2:8000/"
internal const val BACKEND_CONNECT_TIMEOUT_SECONDS = 10L
internal const val BACKEND_WRITE_TIMEOUT_SECONDS = 30L
internal const val BACKEND_READ_TIMEOUT_SECONDS = 180L
internal const val BACKEND_CALL_TIMEOUT_SECONDS = 190L

internal fun createBackendHttpClient(): OkHttpClient =
  OkHttpClient.Builder()
    .connectTimeout(BACKEND_CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
    .writeTimeout(BACKEND_WRITE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
    .readTimeout(BACKEND_READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
    .callTimeout(BACKEND_CALL_TIMEOUT_SECONDS, TimeUnit.SECONDS)
    .retryOnConnectionFailure(false)
    .build()

interface ResponseControlApi {
  @POST("api/v1/generate")
  suspend fun generate(@Body request: GenerateRequestDto): GenerateResponseDto
}

interface ReasoningLabApi {
  @POST("api/v1/reasoning-lab/run")
  suspend fun run(@Body request: ReasoningLabRunRequestDto): ReasoningLabBatchResponseDto
}

interface TemperatureLabApi {
  @POST("api/v1/temperature-lab/run")
  suspend fun run(@Body request: TemperatureLabRunRequestDto): TemperatureLabBatchResponseDto
}

interface ResponseRepository {
  suspend fun generate(prompt: String, controls: GenerationControlsDto): GenerateResponseDto
}

interface ReasoningLabRepository {
  suspend fun run(): ReasoningLabBatchResponseDto
}

interface TemperatureLabRepository {
  suspend fun run(prompt: String): TemperatureLabBatchResponseDto
}

class DefaultResponseRepository(private val api: ResponseControlApi) : ResponseRepository {
  override suspend fun generate(
    prompt: String,
    controls: GenerationControlsDto,
  ): GenerateResponseDto = api.generate(GenerateRequestDto(prompt = prompt, controls = controls))
}

class DefaultReasoningLabRepository(private val api: ReasoningLabApi) : ReasoningLabRepository {
  override suspend fun run(): ReasoningLabBatchResponseDto = api.run(ReasoningLabRunRequestDto())
}

class DefaultTemperatureLabRepository(private val api: TemperatureLabApi) :
  TemperatureLabRepository {
  override suspend fun run(prompt: String): TemperatureLabBatchResponseDto =
    api.run(TemperatureLabRunRequestDto(prompt = prompt))
}

class AppContainer(context: android.content.Context) {
  val compressionSessionStore: CurrentSessionStore = SharedPreferencesCurrentSessionStore(context,
    com.example.responsecontrollab.ui.compression.CompressionLabViewModel.PREFERENCES)
  val tokenSessionStore: CurrentSessionStore = SharedPreferencesCurrentSessionStore(context, "day_08_current_session")
  val currentSessionStore: CurrentSessionStore = SharedPreferencesCurrentSessionStore(context)
  private val json = Json { ignoreUnknownKeys = true }
  private val retrofit =
    Retrofit.Builder()
      .baseUrl(EMULATOR_BACKEND_URL)
      .client(createBackendHttpClient())
      .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
      .build()

  val strategyPreferences: StrategyPreferences = SharedStrategyPreferences(context)
  val contextStrategiesRepository: ContextStrategiesRepository = DefaultContextStrategiesRepository(
    Retrofit.Builder().baseUrl(EMULATOR_BACKEND_URL).client(createBackendHttpClient()).addConverterFactory(Json { ignoreUnknownKeys = true; encodeDefaults = true }.asConverterFactory("application/json".toMediaType())).build().create(ContextStrategiesApi::class.java))

  val compressionLabRepository: CompressionLabRepository = DefaultCompressionLabRepository(
    retrofit.newBuilder().client(createCompressionHttpClient()).build().create(CompressionLabApi::class.java))
  val tokenLabRepository: TokenLabRepository = DefaultTokenLabRepository(retrofit.create(TokenLabApi::class.java))

  val chatRepository: ChatRepository = DefaultChatRepository(retrofit.create(ChatApi::class.java))

  val modelBenchmarkRepository: ModelBenchmarkRepository = createModelBenchmarkRepository()

  val responseRepository: ResponseRepository =
    DefaultResponseRepository(retrofit.create(ResponseControlApi::class.java))
  val reasoningLabRepository: ReasoningLabRepository =
    DefaultReasoningLabRepository(retrofit.create(ReasoningLabApi::class.java))
  val temperatureLabRepository: TemperatureLabRepository =
    DefaultTemperatureLabRepository(retrofit.create(TemperatureLabApi::class.java))
}
