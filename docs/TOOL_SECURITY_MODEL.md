# Tool security model

LifeSandbox uses an explicit registry to describe callable tools. Tool discovery should be limited to the allowlist for the current request, and execution must independently check that the requested tool is authorized.

Tool arguments are validated before dispatch. Unknown fields and invalid types should fail closed. Tool descriptions and returned web/email/file content are untrusted input; they must never override system policy or grant new permissions.

Read-only tools should be preferred when they can satisfy a request. Mutating or high-risk actions should require a distinct approval step that shows the exact action snapshot. Approval must revalidate ownership, connection status, permissions, and the content snapshot before execution.

A tool being present in the registry does not mean every user or every conversation may execute it. Integration scopes and request-level authorization remain separate controls.
