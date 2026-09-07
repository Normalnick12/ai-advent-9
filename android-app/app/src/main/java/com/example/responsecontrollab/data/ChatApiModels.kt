package com.example.responsecontrollab.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
class CreateChatSessionDto

@Serializable
data class ChatMessageRequestDto(val message: String)

@Serializable
data class ChatSessionDto(
  @SerialName("session_id") val sessionId: String,
  @SerialName("history_turn_count") val historyTurnCount: Int,
)

@Serializable
data class ChatErrorDto(val code: String, val message: String)

@Serializable
data class ChatTurnDto(
  @SerialName("session_id") val sessionId: String,
  @SerialName("request_id") val requestId: String,
  val status: String,
  val reply: String?,
  @SerialName("history_turn_count") val historyTurnCount: Int,
  @SerialName("incomplete_reason") val incompleteReason: String?,
  val error: ChatErrorDto?,
)

@Serializable
internal data class ChatHttpErrorDto(
  @SerialName("request_id") val requestId: String,
  val error: ChatErrorDto,
)
