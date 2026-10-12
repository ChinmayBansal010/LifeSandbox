# Workflow, tools and skills

LangGraph is the primary runtime. Its typed `ConversationState` moves from intent and skill selection to an LLM supervisor agent. The agent receives the conversation history, relevant skill instructions and an allowlisted tool catalog. It can request a tool call; LangGraph executes only registered local tools, appends their result, and returns control to the LLM for the user-facing response. The loop is bounded to two tool rounds. The LLM, rather than application code, interprets the user's request and makes recommendations.

Skills are a code-owned allowlist with descriptions, applicability keywords and instructions. Selection is deterministic; user/document text cannot register code or expand permissions. The current six skills are budgeting, career, education, purchasing, travel and time management. The `compare_allocations` tool adds up categories supplied by the LLM and checks them against an available total; it does not choose a winner or write advice. There is no arbitrary shell, SQL or Python tool.

Research is not yet wired into the chat tool loop; it remains available through the separate research API when configured. No external NeMo Agent Toolkit integration or harness comparison is implemented. LangGraph state checkpointing and interrupted run resume remain unfinished.
