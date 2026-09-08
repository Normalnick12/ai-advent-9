package com.example.responsecontrollab

import android.content.Context
import android.content.ContextWrapper
import android.content.SharedPreferences
import android.os.Looper
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.responsecontrollab.data.SharedPreferencesCurrentSessionStore
import java.lang.reflect.Proxy
import java.util.UUID
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CurrentSessionStoreTest {
  @Test fun realPrivatePreferencesRoundTripAcrossInstancesAndClearOffMainThread() = runBlocking {
    val original = ApplicationProvider.getApplicationContext<Context>()
    val name = "test_day07_${UUID.randomUUID()}"
    val threads = mutableListOf<Boolean>()
    val context = object : ContextWrapper(original) {
      override fun getApplicationContext(): Context = this
      override fun getSharedPreferences(file: String, mode: Int): SharedPreferences {
        threads += Looper.myLooper() != Looper.getMainLooper()
        assertEquals(Context.MODE_PRIVATE, mode)
        assertEquals(name, file)
        return super.getSharedPreferences(file, mode)
      }
    }
    try {
      val first = SharedPreferencesCurrentSessionStore(context, name)
      assertNull(first.read())
      val id = UUID.randomUUID().toString()
      first.save(id)
      val second = SharedPreferencesCurrentSessionStore(context, name)
      assertEquals(id, second.read())
      assertEquals(mapOf("session_id" to id), original.getSharedPreferences(name, Context.MODE_PRIVATE).all)
      second.clear()
      assertNull(SharedPreferencesCurrentSessionStore(context, name).read())
      assertEquals(5, threads.size)
      assertTrue(threads.all { it })
    } finally {
      original.deleteSharedPreferences(name)
    }
  }

  @Test fun readExceptionAndFalseCommitAreReported() = runBlocking {
    val original = ApplicationProvider.getApplicationContext<Context>()
    val editor = Proxy.newProxyInstance(SharedPreferences.Editor::class.java.classLoader,
      arrayOf(SharedPreferences.Editor::class.java)) { proxy, method, _ ->
      when (method.name) { "commit" -> false; else -> proxy }
    } as SharedPreferences.Editor
    val preferences = Proxy.newProxyInstance(SharedPreferences::class.java.classLoader,
      arrayOf(SharedPreferences::class.java)) { _, method, _ ->
      when (method.name) { "edit" -> editor; else -> throw IllegalStateException("Read failed") }
    } as SharedPreferences
    val context = object : ContextWrapper(original) {
      override fun getApplicationContext(): Context = this
      override fun getSharedPreferences(name: String, mode: Int) = preferences
    }
    val store = SharedPreferencesCurrentSessionStore(context, "isolated")
    assertTrue(runCatching { store.read() }.isFailure)
    assertTrue(runCatching { store.save("id") }.isFailure)
    assertTrue(runCatching { store.clear() }.isFailure)
  }
}
