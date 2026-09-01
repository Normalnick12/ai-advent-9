# Backend rules

- Keep the Day 02 backend small: FastAPI, Pydantic, and the official OpenAI Python SDK only.
- Use the OpenAI Responses API and keep the requested `gpt-5.6` model alias.
- Read credentials only from `OPENAI_API_KEY`. Never log, return, or commit secrets.
- Keep transport models separate from OpenAI response normalization so controls remain independently testable.
- Return incomplete and upstream error information in the API contract instead of crashing the Android client.
- Add or update tests whenever response controls or the public API contract change.
