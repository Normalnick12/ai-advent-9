package com.example.responsecontrollab.data

import android.content.Context
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

interface CurrentSessionStore {
  suspend fun read(): String?
  suspend fun save(sessionId: String)
  suspend fun clear()
}

class SharedPreferencesCurrentSessionStore(
  context: Context,
  private val preferencesName: String = "day_07_current_session",
  private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : CurrentSessionStore {
  private val appContext = context.applicationContext

  override suspend fun read(): String? = withContext(ioDispatcher) {
    preferences().getString(SESSION_ID, null)
  }

  override suspend fun save(sessionId: String): Unit = withContext(ioDispatcher) {
    check(preferences().edit().putString(SESSION_ID, sessionId).commit())
  }

  override suspend fun clear(): Unit = withContext(ioDispatcher) {
    check(preferences().edit().remove(SESSION_ID).commit())
  }

  private fun preferences() = appContext.getSharedPreferences(preferencesName, Context.MODE_PRIVATE)

  private companion object {
    const val SESSION_ID = "session_id"
  }
}
