package com.example.responsecontrollab

import android.content.Context
import android.content.ContextWrapper
import androidx.test.core.app.ApplicationProvider
import com.example.responsecontrollab.data.*
import org.junit.Assert.*
import org.junit.Test

class DependencyWatchReceiptStoreTest {
  @Test fun committedReceiptReopensWithAllIdsAndLastKnownSelection() {
    val base = ApplicationProvider.getApplicationContext<Context>()
    val context = object : ContextWrapper(base) {
      override fun getSharedPreferences(name: String, mode: Int) = super.getSharedPreferences("test_day18_" + name, mode)
    }
    val prefs = context.getSharedPreferences("day18_watch_receipts_v1", Context.MODE_PRIVATE)
    prefs.edit().clear().commit()
    try {
      val first = WatchFactsDto("one", "g", "a", 3600, 3, "created", "next", "active", 1, 0)
      val snapshot = WatchReceipts(listOf(first, first.copy(watch_id = "two")), "two")
      SharedWatchReceiptStore(context).save(snapshot)
      assertEquals(snapshot, SharedWatchReceiptStore(context).load())
    } finally { prefs.edit().clear().commit() }
  }
}
