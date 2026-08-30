# Eterzion Studio licensing deployment

The `production` branch is a deploy-only contract. The production workflow tests
the licensing service, publishes an immutable GHCR image tagged with the source
commit SHA, and then replaces that branch with only:

- `docker-compose.yml`;
- `.licensing-image.env`;
- `scripts/deploy.sh`;
- `scripts/poll-production-release.sh`.

The VPS poller deploys a new production commit only once. It waits for the
container health check and restores the previous commit and image on failure.
The SQLite database and Ed25519 signing identity live in `storage/`, which is
never replaced or removed by deployment.

## One-time VPS setup

Create `/opt/eterzion-studio-licensing` as a clone of this repository, with the
`origin` remote able to read the private repository. Authenticate Docker to
GHCR with a token that can read packages. Then create the persistent state and
secret configuration:

```bash
sudo install -d -o deploy -g deploy -m 0750 /opt/eterzion-studio-licensing
sudo install -d -o 10001 -g 10001 -m 0700 /opt/eterzion-studio-licensing/storage
sudo -u deploy install -m 0600 \
  /opt/eterzion-studio-licensing/api/astros_licensing_service/.env.example \
  /opt/eterzion-studio-licensing/.env
```

Fill `/opt/eterzion-studio-licensing/.env` with the production provider secrets.
Empty provider secrets keep that integration disabled.

Install the poller after the first production branch exists:

```bash
sudo install -o root -g root -m 0644 \
  deploy/licensing/vps/eterzion-studio-licensing-deploy-poller.service \
  /etc/systemd/system/
sudo install -o root -g root -m 0644 \
  deploy/licensing/vps/eterzion-studio-licensing-deploy-poller.timer \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now eterzion-studio-licensing-deploy-poller.timer
sudo systemctl start eterzion-studio-licensing-deploy-poller.service
```

Verify the pinned release and stable public key:

```bash
cd /opt/eterzion-studio-licensing
printf 'HEAD: '; git rev-parse HEAD
printf 'DEPLOYED: '; cat .deployed-sha
printf 'REMOTE: '; git ls-remote origin refs/heads/production | cut -f1
docker inspect --format '{{.State.Health.Status}}' eterzion-studio-licensing
docker exec eterzion-studio-licensing python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8766/public-key').read().decode())"
```

The reverse proxy must join the existing external `eterzion_proxy` Docker network
and forward `license.eterzion.com` to `eterzion-studio-licensing:8766`. The
container intentionally publishes no host port.
