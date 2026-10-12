# Evaluation

Offline tests assert exact Decimal simulation, invalid scenario rejection, deterministic embeddings, retrieval tenant isolation, chunking boundaries and skill selection. Run `uv run pytest`. Ruff and Pyright are included in CI. No model quality benchmark, NeMo benchmark, LangSmith dataset, latency/cost regression harness, or live provider evaluation is implemented. A passing local suite does not verify Postgres/pgvector, Neon Object Storage, Tavily or model credentials.
