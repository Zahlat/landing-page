# Deploying Meraki

For a step-by-step Oracle Cloud setup with a free trial domain, see [ORACLE.md](ORACLE.md).

Everything runs in containers. Only the edge service is reachable from outside; FastAPI and Postgres stay on a private network.

```
Internet -> edge (Cloudflare Tunnel or Caddy) -> web (Next.js) -> api (FastAPI) -> db (Postgres)
```

| Service | Purpose |
|---|---|
| `web` | Public site and `/admin` |
| `api` | Private FastAPI service |
| `migrate` | Applies database migrations, then exits; `api` waits for it |
| `db` | Postgres (optional: profile `db`) |
| `tunnel` / `caddy` | The edge (choose one) |
| `backup` / `purge` | Maintenance jobs, run on demand |

## What you need

- A server with Docker and the Compose plugin. 1 CPU and 2 GB of RAM is enough to start.
- A domain.
- For a tunnel: a free Cloudflare account with the domain added. For Caddy: ports 80 and 443 open, and the domain's DNS pointing at the server.

## First deployment

```sh
git clone <your-repository> meraki && cd meraki/deploy
cp .env.example .env
nano .env          # fill it in; generate each secret with: openssl rand -hex 32
chmod 600 .env
docker compose up -d --build
docker compose ps  # wait until everything is healthy
docker compose run --rm -it api python -m app.cli create-admin --email you@example.com
```

**Tunnel:** in Cloudflare Zero Trust, create a tunnel, copy its token into `TUNNEL_TOKEN`, and add a public hostname pointing to `http://web:3000`. Set `COMPOSE_PROFILES=db,tunnel` and `TRUSTED_CLIENT_IP_HEADER=cf-connecting-ip`.

**Caddy:** set `COMPOSE_PROFILES=db,caddy`, `SITE_ADDRESS=your-domain.com` and `TRUSTED_CLIENT_IP_HEADER=x-real-ip`.

Then set `SITE_URL=https://your-domain.com`. It is built into the site, so run `docker compose up -d --build` again if it changes.

## Everyday commands

Run these from `deploy/`.

| Task | Command |
|---|---|
| Update | `git pull && docker compose up -d --build` |
| Status / logs | `docker compose ps` / `docker compose logs -f web api` |
| Stop (keeps data) | `docker compose down` |
| Back up database | `docker compose run --rm backup` |
| Remove old visitor data | `docker compose run --rm purge` |
| Scale | Set `WEB_REPLICAS` and `API_REPLICAS` in `.env`, then `docker compose up -d` |

Never add `-v` to `docker compose down` on a server: it deletes the database volume.

Suggested cron entries (`crontab -e`):

```cron
0 2 * * * cd /path/to/meraki/deploy && docker compose run --rm backup
0 3 * * 0 cd /path/to/meraki/deploy && docker compose run --rm purge
```

**Copy `deploy/backups/` off the server regularly.** A backup on the same disk doesn't survive losing the server.

## Restoring a backup

```sh
docker compose stop web api
docker compose cp backups/FILE.dump db:/tmp/restore.dump
docker compose exec db pg_restore -U postgres -d meraki --clean --if-exists --no-owner --role=meraki_app /tmp/restore.dump
docker compose start api web
```

## Growing later

- **Managed database:** remove `db` from `COMPOSE_PROFILES` and set `DATABASE_URL`.
- **More traffic:** raise the replica counts. Rate limits and sessions live in Postgres, so replicas share them.
- **Registry instead of building on the server:** build images in CI, set `WEB_IMAGE` and `API_IMAGE` to a commit tag, then run `docker compose pull && docker compose up -d`. To roll back, set the previous tag.
- **Arm servers:** the images build natively on arm64; building on the server needs no changes.

## After going live (SEO)

1. Set the real `SITE_URL` and rebuild.
2. Verify the domain in [Google Search Console](https://search.google.com/search-console) (the DNS method) and submit `https://your-domain.com/sitemap.xml`. Do the same in Bing Webmaster Tools.
3. Check `/robots.txt`, then test the home page with Google's [Rich Results Test](https://search.google.com/test/rich-results) and [PageSpeed Insights](https://pagespeed.web.dev/).
4. Create a Google Business Profile if your business qualifies, and link the site from your social profiles.
5. When social profiles or a public address exist, add them to `src/components/seo/organization-json-ld.tsx`.
