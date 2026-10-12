# Providers

`ChatModel` normalizes plain chat completions. `LLM_PROVIDER=mock` is the offline default. `nebius` and `openrouter` use their OpenAI-compatible chat-completions HTTP APIs; configure API key and exact model via environment. Requests use bounded HTTP timeout and token limit. Live provider contracts have not been credential-tested. Fallback configuration is reserved but fallback execution is not implemented; errors surface rather than silently switching providers.

`RESEARCH_PROVIDER=tavily` enables Tavily search and normalizes title, URL, limited excerpt, publisher and retrieval time. Disabled or failed research returns an explicit 503. `local_hash` embeddings are deterministic test utilities only. R2 implements short-lived presigned PUT URLs using S3-compatible storage; private-bucket provisioning and object lifecycle are operational requirements. Redis, QStash, LangSmith and Langfuse runtime hooks are not active.
