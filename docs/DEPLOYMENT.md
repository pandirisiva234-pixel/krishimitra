# Deployment

## Option A — Demo on your laptop (recommended for the viva)

Run backend and frontend as in SETUP_WINDOWS.md. Set `PRELOAD_MODELS=true` so the first answer is fast.
For a phone on the same Wi-Fi to use the mic/camera it needs HTTPS. Easiest is a temporary tunnel such as
Cloudflare Tunnel (`cloudflared tunnel --url http://localhost:5173`), which gives a public `https://` address.

## Option B — Docker Compose (any machine with Docker Desktop, or a Linux server)

```powershell
copy .env.docker.example .env      # in the project root; fill in passwords and keys
docker compose up -d --build       # first build downloads PyTorch etc. (10–20 min)
docker compose logs -f backend     # wait for "KrishiMitra API started"
docker compose exec backend python -m scripts.create_admin --name "Admin" --phone 9876543210
```

Open <http://localhost>. Copy `disease_model.onnx` and `disease_labels.json` into `trained_models/` (mounted
into the container) and run `docker compose restart backend`.

| Piece | Where it lives | Persisted by |
| --- | --- | --- |
| PostgreSQL | `db` container | `pgdata` volume |
| ChromaDB index + PDFs | `./knowledge_base` on the host | bind mount |
| Trained models + model cache | `./trained_models` on the host | bind mount (models download once) |
| Uploads + generated audio | `storage` volume | volume |
| Secrets | `.env` on the host (not in images) | – |

## Option C — Public server with HTTPS

1. A VPS with **at least 8 GB RAM** (4 vCPU recommended); Ubuntu 24.04; Docker installed.
2. Point a domain's DNS A-record to the server's IP.
3. In `.env` set `DOMAIN=your.domain`, `PUBLIC_URL=https://your.domain`.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

Caddy obtains and renews a Let's Encrypt certificate automatically. Only ports 80 and 443 are exposed;
PostgreSQL and the backend are reachable only inside the Docker network.

## Production checklist

- [ ] Strong `POSTGRES_PASSWORD` and a new random `JWT_SECRET_KEY`
- [ ] `.env` readable only by the deploy user (`chmod 600 .env`)
- [ ] `ENVIRONMENT=production`, `CORS_ORIGINS` = your exact site address
- [ ] Gemini API key restricted to the Generative Language API in Google Cloud console
- [ ] Backups scheduled: `deploy/backup.sh` via cron (keeps 14 days); test a restore once
- [ ] Logs: `docker compose logs --since 1h backend`; every line has a request ID to trace errors
- [ ] Monitoring: admin → *Admin overview* → System status; `GET /api/health` for uptime checks
- [ ] Update: `git pull && docker compose up -d --build` (migrations run automatically at start)

## Scaling notes (for the report's "future enhancements")

The backend runs one worker because each worker would load ~3 GB of models. To serve more users: move
Whisper/NLLB into a separate GPU inference service, run several API workers that call it, and put Redis in
front of the rate limiter so limits are shared across workers.
