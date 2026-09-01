package com.example.responsecontrollab

import android.app.Application
import com.example.responsecontrollab.data.AppContainer

class ResponseControlApplication : Application() {
  val container: AppContainer by lazy { AppContainer() }
}
