## Proxy server

`proxy.py` exposes a small FastAPI app that forwards requests to local services:

- `/snapsave/api/*` → `http://127.0.0.1:8001/*`
- `/ollama/api/*` → `http://127.0.0.1:1456/*`
- `/label_studio/api/*` → `http://127.0.0.1:30001/*`

Run it with uvicorn:

```bash
uv run uvicorn proxy:app --host 0.0.0.0 --port 8000
```

### Routing
- Requests are routed by prefix: `/snapsave/*`, `/ollama/*`, `/label_studio/*`.
- Absolute paths are routed by alias: if only one upstream owns the alias (e.g., `/static`, `/react-app`, `/api` currently belong to Label Studio), it forwards there; if multiple upstreams share an alias, the request is only forwarded when the `Referer` contains that upstream’s prefix to avoid cross-service poisoning.
- Redirects coming from an upstream are rewritten to stay under the public prefix (e.g., Label Studio redirects to `/projects/...` are rewritten to `/label_studio/projects/...`).
- Redirects are handled by the proxy (httpx does not auto-follow), so clients always see rewritten `Location` headers.
