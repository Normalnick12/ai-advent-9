package com.example.responsecontrollab.data

import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface ModelBenchmarkApi {
  @GET("api/v1/model-benchmark/catalog")
  suspend fun catalog(): ModelBenchmarkCatalogDto

  @POST("api/v1/model-benchmark/run")
  suspend fun run(@Body request: ModelBenchmarkRunRequestDto): ModelBenchmarkBatchDto
}

interface ModelBenchmarkRepository {
  suspend fun catalog(): ModelBenchmarkCatalogDto
  suspend fun run(models: Map<String, String>): ModelBenchmarkBatchDto
}

class DefaultModelBenchmarkRepository(private val api: ModelBenchmarkApi) : ModelBenchmarkRepository {
  override suspend fun catalog(): ModelBenchmarkCatalogDto = api.catalog()
  override suspend fun run(models: Map<String, String>): ModelBenchmarkBatchDto =
    api.run(ModelBenchmarkRunRequestDto(models.toMap()))
}

internal fun createModelBenchmarkHttpClient(): OkHttpClient =
  OkHttpClient.Builder()
    .connectTimeout(10, TimeUnit.SECONDS)
    .writeTimeout(30, TimeUnit.SECONDS)
    .readTimeout(260, TimeUnit.SECONDS)
    .callTimeout(300, TimeUnit.SECONDS)
    .retryOnConnectionFailure(false)
    .build()

internal fun createModelBenchmarkRepository(): ModelBenchmarkRepository {
  val retrofit = Retrofit.Builder()
    .baseUrl("http://10.0.2.2:8000/")
    .client(createModelBenchmarkHttpClient())
    .addConverterFactory(Json { ignoreUnknownKeys = true }.asConverterFactory("application/json".toMediaType()))
    .build()
  return DefaultModelBenchmarkRepository(retrofit.create(ModelBenchmarkApi::class.java))
}
