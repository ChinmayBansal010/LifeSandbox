interface Env {
  API_ORIGIN: string
}

/**
 * Keep the browser on the Pages origin while the API runs on Cloud Run.
 * This preserves secure session cookies and lets Google OAuth callbacks use
 * https://<pages-domain>/api/v1/auth/google/callback.
 */
export const onRequest: PagesFunction<Env> = async ({ request, env }) => {
  const origin = env.API_ORIGIN?.replace(/\/$/, '')
  if (!origin) {
    return new Response('The API proxy is not configured.', { status: 503 })
  }

  const incoming = new URL(request.url)
  const headers = new Headers(request.headers)
  headers.delete('host')
  const upstream = new URL(`${origin}${incoming.pathname}`)
  upstream.search = incoming.search
  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: 'manual',
  }
  if (!['GET', 'HEAD'].includes(request.method)) init.body = request.body

  try {
    return await fetch(upstream, init)
  } catch {
    return new Response('The API is temporarily unavailable.', { status: 502 })
  }
}
