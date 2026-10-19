# Frontend state and persistence

The frontend stores conversations, messages, active conversation selection, and theme preference in browser localStorage. This is a convenience for the local-first interface, not encrypted storage. Anyone with access to the browser profile may be able to read the stored content.

The backend also persists conversation history. The frontend's local copy and the server's conversation ID are separate identifiers; do not assume that clearing browser storage deletes server-side data.

When changing the persisted shape:

1. Increment the storage version if the format changes incompatibly.
2. Add a migration from the previous format when feasible.
3. Preserve the active conversation only when its ID exists in the migrated collection.
4. Handle malformed or unavailable storage without preventing the app from starting.
5. Test legacy migration, corrupt JSON, missing fields, and unknown theme values.
6. Document whether the change affects browser-local data, server data, or both.

Do not put API credentials, OAuth refresh tokens, or other secrets in localStorage. Browser-side data should be treated as user-controlled and untrusted when loaded back into the application.
