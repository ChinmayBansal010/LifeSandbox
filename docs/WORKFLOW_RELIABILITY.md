# Workflow reliability

## Request validation

Task and reminder requests validate lengths, priorities, recurrence values, and timezone-aware timestamps before persistence. Project and task references must be owned by the current user.

## Idempotency

Mutating workflow requests may include an idempotency key. Clients should reuse the same key only when retrying the same logical operation and should generate a new key for a different operation. A retry must not be treated as a new user intent.

## Reminder delivery

The worker claims due jobs with a conditional database update, records attempts, and recovers expired leases. Notification creation checks for an existing notification for the job. These controls reduce duplicate delivery under retries; they do not guarantee exactly-once behavior across arbitrary external systems.

## Recurrence and timezones

Store scheduled instants in UTC and preserve the user's IANA timezone for recurrence calculations. Daily and weekly recurrences should advance local calendar time rather than adding fixed UTC durations, because daylight-saving transitions can change UTC offsets.

## Operational checks

Inspect queued, running, failed, and succeeded jobs; alert on repeated failures and expired leases. Keep the worker running separately from the API process in deployments that use durable reminders.
