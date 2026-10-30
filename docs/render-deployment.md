# Render deployment

This deployment uses Render for the FastAPI API, Neon for the existing database, OpenRouter for inference, and Cloudflare Pages for the existing React frontend and same-origin API proxy.

## Before you start

Keep `.env` private. The values are entered in Render's secret form and are never committed. The `render.yaml` Blueprint is intentionally limited to the API: Render's free web services can sleep after inactivity, so the scheduled worker is not deployed on this plan. The image startup script runs Alembic migrations and then binds FastAPI to Render's `PORT`.

## Deploy the API

1. Sign in to Render with the GitHub account that can access `ChinmayBansal010/LifeSandbox`.
2. Select **New** -> **Blueprint** and choose this repository and the `main` branch. Render detects `render.yaml`.
3. Render prompts for every variable marked as a private input. Copy the corresponding value from your existing `.env` file, including values that are intentionally blank. The Blueprint now declares every key in the local environment while keeping all values out of Git.

   The most important startup values are:

   - `DATABASE_URL`
   - `OPENROUTER_API_KEY`
   - `OPENROUTER_MODEL`
   - `OPENROUTER_FALLBACK_MODEL` (leave blank when it is blank locally)
   - `AUTH_SECRET`
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`

   For the first API deploy, temporarily enter `https://placeholder.invalid` for `GOOGLE_AUTH_CALLBACK_URL`, `GOOGLE_AUTH_FRONTEND_URL`, and `CORS_ORIGINS`. They are replaced once Pages has a public URL.

4. Choose the free plan and create the Blueprint. Wait until the service health check at `/ready` succeeds, then copy its URL, such as `https://lifesandbox-api.onrender.com`.

## Deploy the frontend and connect it

1. In Cloudflare Pages, import the same GitHub repository.
2. Set **Root directory** to `frontend`, **Build command** to `npm run build`, and **Build output directory** to `dist`.
3. The Pages runtime API proxy is configured in `frontend/wrangler.toml` with the public Render origin. If your Render service URL changes, update `API_ORIGIN` in that file and redeploy Pages. In Pages -> Settings -> Variables and Secrets, add only the public build-time support address:

   ```text
   VITE_SUPPORT_EMAIL=your-support-email@example.com
   ```

   Deploy Pages and copy its public URL.

4. In Render -> `lifesandbox-api` -> Environment, replace the three temporary values with:

   ```text
   GOOGLE_AUTH_CALLBACK_URL=https://<your-pages-domain>/api/v1/auth/google/callback
   GOOGLE_AUTH_FRONTEND_URL=https://<your-pages-domain>
   CORS_ORIGINS=["https://<your-pages-domain>"]
   ```

   Save changes and redeploy the API.

5. In Google Cloud Console -> APIs & Services -> Credentials -> your OAuth web client, add this exact authorized redirect URI:

   ```text
   https://<your-pages-domain>/api/v1/auth/google/callback
   ```

## Verify

Open these URLs after both deployments complete:

```bash
curl -fsS https://lifesandbox-api.onrender.com/ready
curl -fsS https://<your-pages-domain>/api/v1/capabilities
```

Then open the Pages URL, sign in with Google, send one chat message, create a task, and create a reminder. The API uses OpenRouter from the server side; the browser never receives the provider key.

## Free-plan behavior

Render free web services can spin down after idle time, so the first request after inactivity can take about a minute. The free API also does not provide an always-on worker; reminders are stored correctly but should not be treated as guaranteed scheduled delivery until you move the worker to an always-on scheduler or paid service.
