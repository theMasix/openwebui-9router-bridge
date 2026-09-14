# OpenWebUI to 9Router Search Bridge

High-performance, production-ready translation proxy connecting Open WebUI's External Web Search protocol (`POST /search`) to 9Router's search endpoint (`POST /v1/search`).

---

## Architecture

Open WebUI External Search sends queries using `{ "query": "...", "count": 5 }` and expects a JSON array of `[{ "link": "...", "title": "...", "snippet": "..." }]`.

9Router exposes an OpenAI-compatible web search API at `POST /v1/search` taking `{ "model": "...", "query": "...", "max_results": 5 }` and returning `{ "results": [{ "url": "...", "title": "...", "snippet": "..." }] }`.

This bridge:
1. Validates inbound requests from Open WebUI (optional Bearer token).
2. Maps `count` -> `max_results` and injects upstream `model` (e.g. `tavily`, `brave`, `searxng`, or combo).
3. Authenticates against 9Router (optional Bearer token).
4. Handles retries with exponential backoff on transient upstream errors.
5. Remaps response fields (`url` -> `link`) to Open WebUI's expected schema.

```
┌──────────────┐   POST /search       ┌────────────────────────┐   POST /v1/search    ┌─────────────┐
│ Open WebUI   │ ───────────────────> │ openwebui-9router-     │ ───────────────────> │ 9Router     │
│              │ <─────────────────── │ bridge                 │ <─────────────────── │             │
└──────────────┘   [{link,title,...}] └────────────────────────┘   {results:[{url}]}  └─────────────┘
```

---

## Configuration

All configuration is handled via environment variables:

| Variable | Default | Description |
|---|---|---|
| `BRIDGE_HOST` | `0.0.0.0` | Listen host interface |
| `BRIDGE_PORT` | `8000` | Listen port |
| `BRIDGE_LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `BRIDGE_INBOUND_API_KEY` | `""` | Optional Bearer token Open WebUI must send |
| `BRIDGE_NINEROUTER_URL` | `http://localhost:20128` | 9Router base URL |
| `BRIDGE_NINEROUTER_API_KEY`| `""` | Optional Bearer token for 9Router |
| `BRIDGE_SEARCH_MODEL` | `tavily` | Provider/model name configured in 9Router |
| `BRIDGE_TIMEOUT_SECONDS` | `15.0` | Upstream timeout in seconds |
| `BRIDGE_MAX_RETRIES` | `2` | Upstream retry count on transient errors (429, 5xx) |

Aliases like `NINEROUTER_URL`, `NINEROUTER_KEY`, `SEARCH_MODEL`, and `BRIDGE_API_KEY` are also supported.

---

## Quickstart (Local / uv)

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install dependencies
git clone https://github.com/your-org/openwebui-9router-bridge.git
cd openwebui-9router-bridge
uv sync

# Run bridge
export BRIDGE_NINEROUTER_URL="http://localhost:20128"
export BRIDGE_SEARCH_MODEL="tavily"
uv run openwebui-9router-bridge
```

---

## Docker

### Build Image
```bash
docker build -t openwebui-9router-bridge:latest .
```

### Run Container
```bash
docker run -d \
  --name openwebui-9router-bridge \
  -p 8000:8000 \
  -e BRIDGE_NINEROUTER_URL="http://host.docker.internal:20128" \
  -e BRIDGE_SEARCH_MODEL="tavily" \
  -e BRIDGE_INBOUND_API_KEY="my-secret-key" \
  openwebui-9router-bridge:latest
```

---

## Open WebUI Setup

1. Open WebUI -> **Admin Panel** -> **Settings** -> **Web Search**.
2. Toggle **Enable Web Search** to `ON`.
3. Set **Web Search Engine** to `external`.
4. Set **External Search URL** to:
   ```
   http://<bridge-host>:8000/search
   ```
5. If `BRIDGE_INBOUND_API_KEY` is configured, enter it into **External Search API Key**.
6. Click **Save**.

---

## Kubernetes / Helm

Deploy using the provided Helm chart:

```bash
helm install search-bridge ./charts/openwebui-9router-bridge \
  --set bridge.ninerouterUrl="http://ninerouter.default.svc.cluster.local:20128" \
  --set bridge.searchModel="tavily" \
  --set bridge.inboundApiKey="secret-token"
```

See [`charts/openwebui-9router-bridge/values.yaml`](charts/openwebui-9router-bridge/values.yaml) for full configuration.

---

## Testing

```bash
uv run pytest -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
