FOLLOWTHROUGH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Read this user's persisted tasks, optionally filtered by status.",
            "parameters": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a reversible task the user explicitly requested.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "project_id": {"type": ["string", "null"]},
                    "priority": {"type": "string", "enum": ["low", "normal", "high"]},
                    "due_at": {
                        "type": ["string", "null"],
                        "description": "ISO 8601 time with offset",
                    },
                    "timezone": {"type": "string", "description": "IANA timezone"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update a persisted task owned by this user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "project_id": {"type": ["string", "null"]},
                    "priority": {"type": "string", "enum": ["low", "normal", "high"]},
                    "due_at": {"type": ["string", "null"]},
                    "timezone": {"type": "string"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark one of this user's tasks completed.",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_task",
            "description": "Cancel a pending task without deleting its history.",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Read this user's persisted reminders.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Schedule an in-app reminder at a user-specified timezone-aware time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "scheduled_at": {"type": "string", "description": "ISO 8601 time with offset"},
                    "timezone": {"type": "string", "description": "IANA timezone"},
                    "task_id": {"type": ["string", "null"]},
                    "recurrence": {"type": "string", "enum": ["none", "daily", "weekly"]},
                },
                "required": ["text", "scheduled_at", "timezone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_reminder",
            "description": "Update a pending reminder's time, timezone, text, or recurrence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string"},
                    "text": {"type": "string"},
                    "scheduled_at": {"type": "string"},
                    "timezone": {"type": "string"},
                    "recurrence": {"type": "string", "enum": ["none", "daily", "weekly"]},
                },
                "required": ["reminder_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reminder",
            "description": "Cancel a pending reminder and its queued job.",
            "parameters": {
                "type": "object",
                "properties": {"reminder_id": {"type": "string"}},
                "required": ["reminder_id"],
            },
        },
    },
]

FOLLOWTHROUGH_TOOL_NAMES = {tool["function"]["name"] for tool in FOLLOWTHROUGH_TOOLS}
