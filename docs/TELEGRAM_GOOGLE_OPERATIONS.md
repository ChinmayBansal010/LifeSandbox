# Telegram Bot & Google Services Operations Guide

This document explains how the Telegram bot integrates with Google services (Google Calendar, Gmail, Google Drive) and how all operations are handled from Telegram.

---

## 1. Environment Configuration

All settings are read dynamically from `.env` via `app.core.config.Settings`. Nothing is hardcoded.

```env
# Telegram
TELEGRAM_BOT_TOKEN=<your-bot-token>
TELEGRAM_CHAT_ID=<your-chat-id>
TELEGRAM_ALLOWED_CHAT_IDS=<optional-comma-separated-chat-ids>
TELEGRAM_DEFAULT_USER_ID=local-user
TELEGRAM_POLLING_ENABLED=true

# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=<your-client-id>
GOOGLE_OAUTH_CLIENT_SECRET=<your-client-secret>
GOOGLE_OAUTH_CALLBACK_URL=http://localhost:8000/api/v1/integrations/google/callback
GOOGLE_TOKEN_ENCRYPTION_KEY=<fernet-base64-key>
```

---

## 2. Supported Operations from Telegram

### 📅 Google Calendar
* **View Events:** `"What are my events today?"` or `"Show my calendar for next week"` (`calendar.list_events`)
* **Find Free Slots:** `"Find a 45-minute slot tomorrow afternoon"` (`calendar.find_free_time`)
* **Create Event:** `"Schedule a meeting with Alex on Friday at 3pm UTC about Project Launch"` (`calendar.create_event`)
* **Update / Reschedule:** `"Move my 3pm meeting on Friday to 4pm"` (`calendar.update_event`)
* **Delete / Cancel:** `"Cancel my 4pm meeting on Friday"` (`calendar.delete_event`)

### ✉️ Gmail
* **Search Emails:** `"Find emails from Alice about invoice"` (`gmail.search_messages`)
* **Read Email Threads:** `"Read the thread with subject Q4 budget"` (`gmail.get_thread`)
* **Send Email Directly:** `"Send an email to alex@example.com with subject Update and body We are on track"` (`gmail.send_message`)
* **Reply to Thread:** `"Reply to the latest email from Sarah saying sounds great"` (`gmail.reply_to_thread`)
* **Create Draft & Approve:** `"Draft an email to Bob asking for the report"` (`gmail.create_draft` + `gmail.send_draft`)
* **Trash Email:** `"Delete the email with ID xyz"` (`gmail.trash_message`)
* **Organize / Labels:** `"Mark the email as read"` or `"Archive that newsletter"` (`gmail.modify_labels`)

### 📁 Google Drive
* **Search Files:** `"Search my drive for the Q3 roadmap slides"` (`drive.search_files`)
* **Read Content:** `"Read the text in the file Q3 roadmap"` (`drive.get_file_content`)
* **Create Files / Docs:** `"Create a new Google Doc named Meeting Notes with content Kickoff discussion summary"` (`drive.create_file`)
* **Edit Content:** `"Update the document Meeting Notes with the new action items"` (`drive.update_file_content`)
* **Delete Files:** `"Trash the old notes document"` (`drive.delete_file`)
* **Create Folders:** `"Create a new folder in Drive named Project Alpha"` (`drive.create_folder`)

---

## 3. Telegram Management Commands

* `/connect_google` or `/auth_google`: Generates a secure, 10-minute Google OAuth authorization link directly in Telegram chat to link or re-consent your Google account.
* `/google_status`: Inspects active Google connections, account email, status, and granted scopes.
* `/approvals` or `/pending`: Lists any high-risk actions waiting for your approval.
* `/approve <approval_id>`: Confirms and executes an approval action immediately from Telegram.
* `/reject <approval_id>`: Rejects an action proposal.
* `/status`: Displays bot and LLM health status.
* `/new` or `/reset`: Clears chat context and starts a fresh conversation.
* `/help`: Displays the full command and capability menu.

---

## 4. Starting the Server

To run the backend with Telegram long-polling enabled:

```bash
cd LifeSandbox
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```
