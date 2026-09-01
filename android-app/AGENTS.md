# Android app rules

- Keep a single `app` module with Kotlin, Jetpack Compose, and Material 3.
- Use simple MVVM: a screen-level ViewModel calls a Repository through constructor injection.
- Keep object creation in `AppContainer`; do not add Dagger or Hilt unless a later Day requires it.
- Use Retrofit with `kotlinx.serialization` and coroutines for the local backend API.
- The Android app must never contain or request `OPENAI_API_KEY`; all OpenAI calls go through FastAPI.
- The emulator backend URL is `http://10.0.2.2:8000/`.
- Permit cleartext HTTP only in debug resources for the local emulator backend.
- Preserve the identical prompt value for FREE and CONTROLLED calls in COMPARE mode.
- Keep UI states explicit: loading, error, results, and retry through Generate.
