# Deploying to Oracle Cloud (free tier) with a free trial domain

This first trial uses:

- **Oracle Cloud Always Free:** an Arm (Ampere A1) Ubuntu server.
- **DuckDNS:** a free hostname such as `meraki-trial.duckdns.org`.
- **Caddy:** HTTPS from Let's Encrypt, from the `caddy` profile in `compose.yaml`.

Cloudflare Tunnel isn't used here because it needs a domain you own. It's covered under "Moving to a real domain" below.

> Oracle's console changes often. If a menu name below differs, look for the closest match.

## 1. On your PC: create an SSH key (once)

In PowerShell:

```powershell
ssh-keygen -t ed25519 -f $HOME\.ssh\oracle_meraki
Get-Content $HOME\.ssh\oracle_meraki.pub   # you'll paste this into Oracle
```

Keep `oracle_meraki` (without `.pub`) private. It is the key to your server.

## 2. Create the Oracle account

1. Sign up at <https://www.oracle.com/cloud/free/> with your **real** details. Using a VPN or a false address can get the account, and everything on it, closed.
2. **Choose the home region carefully: it can't be changed**, and free servers can only be created there. Pick the region nearest your visitors.
3. Oracle asks for a card to verify you. Always Free resources aren't charged.

## 3. Create the server

**Compute → Instances → Create instance**

| Setting | Value |
|---|---|
| Image | Canonical Ubuntu 24.04 (the aarch64 build) |
| Shape | Ampere → `VM.Standard.A1.Flex`, **1 OCPU, 6 GB** memory |
| Networking | Create a new virtual cloud network with a public subnet; assign a public IPv4 address |
| SSH keys | Paste the contents of `oracle_meraki.pub` |
| Boot volume | Default (about 50 GB) is enough |

Note the **public IP address** once it's running.

- If you see **"Out of host capacity"**, there is no free Arm capacity in your region right now. Try another availability domain, or try again later.
- Oracle can reclaim a free server that stays idle (under 20% CPU, network *and* memory for 7 days). Backups kept off the server (step 9) protect you either way.

## 4. Open ports 80 and 443 in Oracle's firewall

**Networking → Virtual cloud networks → your network → Security Lists → Default Security List → Add Ingress Rules**

Add two rules: source `0.0.0.0/0`, protocol TCP, destination port `80`, then the same for `443`.

## 5. Get the free hostname

1. Log in at <https://www.duckdns.org>.
2. Create a subdomain, for example `meraki-trial`.
3. Put your server's public IP in its **current ip** field and click **update ip**.

Your address is now `meraki-trial.duckdns.org`.

## 6. Prepare the server

```powershell
ssh -i $HOME\.ssh\oracle_meraki ubuntu@YOUR_SERVER_IP
```

Then, on the server:

```sh
# Updates, plus automatic security updates
sudo apt update && sudo apt -y upgrade
sudo apt -y install unattended-upgrades git

# Oracle's Ubuntu images block everything except SSH in the server firewall too
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

# Docker (official install script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit
```

Log in again (so the `docker` group applies), then run `docker version` to check.

## 7. Get the code onto the server

If the GitHub repository is **private**, give the server read-only access with a deploy key:

```sh
ssh-keygen -t ed25519 -N "" -f ~/.ssh/github_deploy
cat ~/.ssh/github_deploy.pub
```

Add that key in GitHub under **repository → Settings → Deploy keys → Add deploy key** (leave write access off). Then:

```sh
cat >> ~/.ssh/config <<'EOF'
Host github.com
  IdentityFile ~/.ssh/github_deploy
EOF
git clone git@github.com:Zahlat/landing-page.git meraki
```

If the repository is public: `git clone https://github.com/Zahlat/landing-page.git meraki`

## 8. Configure and start

```sh
cd ~/meraki/deploy
cp .env.example .env
for key in INTERNAL_TOKEN FORM_SIGNING_SECRET IP_HASH_SECRET POSTGRES_PASSWORD APP_DB_PASSWORD; do
  sed -i "s/^$key=.*/$key=$(openssl rand -hex 32)/" .env
done
chmod 600 .env
nano .env
```

In `nano`, set these four lines (use your own hostname):

```ini
COMPOSE_PROFILES=db,caddy
SITE_URL=https://meraki-trial.duckdns.org
SITE_ADDRESS=meraki-trial.duckdns.org
TRUSTED_CLIENT_IP_HEADER=x-real-ip
```

Then start everything. The first build takes a while on one CPU.

```sh
docker compose up -d --build
docker compose ps                  # wait until web and api show "healthy"
docker compose logs caddy | grep -i certificate   # should mention obtaining a certificate
docker compose run --rm -it api python -m app.cli create-admin --email you@example.com
```

Open `https://meraki-trial.duckdns.org`, send a test message from `/ar/contact`, and check it arrives in `/admin`.

## 9. Backups (do this on day one)

On the server, run `crontab -e` and add:

```cron
0 2 * * * cd /home/ubuntu/meraki/deploy && docker compose run --rm backup
0 3 * * 0 cd /home/ubuntu/meraki/deploy && docker compose run --rm purge
```

Copy backups to your PC regularly, because a backup on the same server is lost with the server. In PowerShell:

```powershell
scp -i $HOME\.ssh\oracle_meraki "ubuntu@YOUR_SERVER_IP:~/meraki/deploy/backups/*" .
```

## 10. Everyday use

| Task | On the server, in `~/meraki/deploy` |
|---|---|
| Deploy new code | `git pull && docker compose up -d --build` |
| Status / logs | `docker compose ps` / `docker compose logs -f web api` |
| Memory use | `docker stats --no-stream` |
| Restore a backup | See "Restoring a backup" in `README.md` |

## While on the trial domain

- Don't submit the trial address to Google Search Console. Wait for the real domain, so search engines don't index a temporary one.
- If DuckDNS fails to get a certificate, check that ports 80/443 are open (steps 4 and 6) and that DuckDNS shows the current server IP.

## Moving to a real domain later

**Option A, keep Caddy:**
1. Point the domain's DNS `A` record at the server IP.
2. Set `SITE_URL=https://your-domain.com` and `SITE_ADDRESS=your-domain.com`.
3. Run `docker compose up -d --build`. Caddy gets a new certificate by itself.

**Option B, Cloudflare Tunnel** (no open ports at all):
1. Add the domain to Cloudflare and create a tunnel with a public hostname pointing to `http://web:3000`.
2. Set `COMPOSE_PROFILES=db,tunnel`, `TUNNEL_TOKEN`, `TRUSTED_CLIENT_IP_HEADER=cf-connecting-ip` and the new `SITE_URL`.
3. Rebuild, then remove the port 80/443 rules from step 4.
