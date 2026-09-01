package com.example.responsecontrollab.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class BackendHttpClientTest {
  @Test
  fun timeoutBudgetCoversTheBoundedBackendRetryBudget() {
    val client = createBackendHttpClient()

    assertEquals(10_000, client.connectTimeoutMillis)
    assertEquals(30_000, client.writeTimeoutMillis)
    assertEquals(180_000, client.readTimeoutMillis)
    assertEquals(190_000, client.callTimeoutMillis)
    assertFalse(client.retryOnConnectionFailure)
  }
}
