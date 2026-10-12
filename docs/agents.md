# Workflow, tools and skills

LangGraph is the primary runtime. Its typed `ConversationState` moves through a lightweight intent/skill classifier and response node. Simple requests invoke no specialist subagents. Intent labels can include conversation, research or simulation, but automatic research/simulation tool routing is not yet connected to chat; callers use their typed APIs directly.

Skills are a code-owned allowlist with descriptions, applicability keywords, instructions and permitted tool names. Selection is deterministic; user/document text cannot register code or expand permissions. The current six skills are budgeting, career, education, purchasing, travel and time management. There is no arbitrary shell, SQL or Python tool.

No external NeMo Agent Toolkit integration or harness comparison is implemented. Offline deterministic tests cover the simulator, skill routing and tenant-filtered retrieval. LangGraph state checkpointing and interrupted run resume remain unfinished.
