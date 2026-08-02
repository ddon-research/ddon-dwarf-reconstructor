# Langfuse Agent Tracing

This project includes a local Langfuse deployment for tracing GitHub Copilot in VS Code and
OpenAI Codex running in WSL2. The Python application is not instrumented. The deployment stores
traces locally in Docker volumes and exposes the Langfuse UI and OTLP ingestion endpoint only on
loopback interfaces.

## Architecture

| Component | Local address | Purpose |
| --- | --- | --- |
| Langfuse web | `http://localhost:3000` | UI and OTLP HTTP ingestion |
| MinIO API | `http://localhost:9090` | Local media upload endpoint |
| PostgreSQL | Compose network only | Langfuse application data |
| ClickHouse | Compose network only | Trace and event analytics |
| Redis | Compose network only | Langfuse queue and cache |
| MinIO console | Compose network only | Object storage administration |

The Compose stack uses health-gated dependencies, named volumes, and `unless-stopped` restart
policies. The volume names are stable: `ddon-langfuse-postgres`, `ddon-langfuse-clickhouse`,
`ddon-langfuse-clickhouse-logs`, `ddon-langfuse-minio`, and `ddon-langfuse-redis`.

## Prerequisites

- Windows 11 with Docker Desktop and the WSL2 engine enabled.
- WSL integration enabled for the Linux distribution used by Codex.
- Docker Desktop configured to start when you sign in to Windows.
- PowerShell 5.1 or newer.
- Node.js 22 or newer and Codex 0.128 or newer for Codex tracing.

Docker Desktop must be running before the Compose commands. The current setup was validated with
Docker Compose `v5.3.1`.

## Start Langfuse

Run these commands from the repository root in PowerShell:

```powershell
Copy-Item ops/langfuse/.env.example ops/langfuse/.env
# Replace the REPLACE_WITH values in ops/langfuse/.env.
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env config --quiet
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env up -d
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env logs --tail 200 langfuse-web
```

The `.env` file is ignored by Git and must contain local service credentials. The Compose file does
not run headless user/project initialization; create the first account and project in the Langfuse
UI after startup. `up -d` intentionally does not wait on the web service health state. Use the web
logs and `http://localhost:3000` to confirm that Langfuse is ready.

The equivalent Make targets are:

```text
make langfuse-config
make langfuse-up
make langfuse-logs
make langfuse-status
```

Open <http://localhost:3000> and create a local account and project. Copy the project's public and
secret API keys from the project settings. Create the account and project in the UI before
configuring Copilot or Codex.

## Windows Auto-start

Docker Compose cannot turn on Docker Desktop's Windows sign-in setting. Configure that once in
Docker Desktop:

1. Open **Settings > General**.
2. Enable **Start Docker Desktop when you sign in to your computer**.
3. Open **Settings > Resources > WSL Integration** and enable the distribution used by Codex.
4. Run the Compose `up -d` command from the start section once.

Every service uses `restart: unless-stopped`. When Docker Desktop or Windows restarts, the Docker
daemon restores the stack automatically because the containers were not explicitly stopped.

Use these lifecycle commands deliberately:

```powershell
# Stop containers temporarily. Named volumes remain intact.
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env stop

# Start containers that already exist.
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env up -d

# Remove containers and the Compose network but preserve all trace data.
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env down

# Remove containers and all Langfuse data. This is destructive.
docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env down --volumes
```

Do not use `down -RemoveVolumes` for routine cleanup. Back up the Docker volumes before deleting
or migrating the local instance.

## Configure VS Code Copilot per repository

GitHub Copilot exports OpenTelemetry spans directly to Langfuse. No SDK, proxy, or application code
change is required.

Copilot's OTEL settings are application-scoped in VS Code. That means `.vscode/settings.json`
cannot override them, and a Windows-level `OTEL_EXPORTER_OTLP_HEADERS` value would accidentally
send every repository to the same Langfuse project. Use a separate VS Code profile for each
repository instead.

Create or open this repository with its profile:

```powershell
code --profile "ddon-dwarf-reconstructor-langfuse" --new-window .
```

In that profile's **User** `settings.json`, configure this repository's Langfuse project:

```jsonc
{
  "github.copilot.chat.otel.enabled": true,
  "github.copilot.chat.otel.exporterType": "otlp-http",
  "github.copilot.chat.otel.protocol": "http/json",
  "github.copilot.chat.otel.otlpEndpoint": "http://localhost:3000/api/public/otel",
  "github.copilot.chat.otel.captureContent": true,
  "github.copilot.chat.otel.maxAttributeSizeChars": 0,
  "github.copilot.chat.otel.serviceName": "vscode-copilot-chat-ddon-dwarf-reconstructor",
  "github.copilot.chat.otel.headers": {
    "Authorization": "Basic <base64(public-key:secret-key)>",
    "x-langfuse-ingestion-version": "4"
  }
}
```

Generate the Basic Auth value locally from this repository's Langfuse public and secret keys:

```powershell
$Pair = "$PublicKey`:$SecretKey"
$Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($Pair))
```

Do not set `OTEL_EXPORTER_OTLP_HEADERS` globally. For another repository, create another profile,
use that repository's Langfuse project keys, and give it a different `serviceName`. Reload or
restart the profile after changing its OTEL settings.

The exporter captures Copilot agent spans, model generations, tool calls, token usage, session
identifiers, and Git context. With content capture enabled it also stores prompts, responses, and
tool arguments.

## Configure Codex in WSL2

Run the plugin commands in the WSL2 distribution where Codex is installed:

```bash
codex plugin marketplace add langfuse/codex-observability-plugin
```

Add this to `~/.codex/config.toml`:

```toml
[features]
plugin_hooks = true

[plugins."tracing@codex-observability-plugin"]
enabled = true
```

Create `~/.codex/langfuse.json` with the API keys from the local Langfuse project:

```json
{
  "enabled": true,
  "public_key": "pk-lf-replace-me",
  "secret_key": "sk-lf-replace-me",
  "base_url": "http://localhost:3000"
}
```

Protect the file in WSL2:

```bash
chmod 600 ~/.codex/langfuse.json
```

Tracing is opt-in. Enable it in the WSL2 shell that starts Codex:

```bash
export TRACE_TO_LANGFUSE=true
export LANGFUSE_CODEX_MAX_CHARS=20000
codex
```

For a persistent setup, add those exports to `~/.bashrc` or the shell profile used by Codex. The
plugin reads the Codex transcript after each turn and fails open if upload fails, so tracing does
not block a Codex session. It captures prompts, assistant messages, reasoning summaries, tool
inputs and outputs, model metadata, token usage, and nested subagent sessions.

Check local connectivity from WSL2 before debugging Codex:

```bash
curl -fsS http://localhost:3000 >/dev/null && echo 'Langfuse is reachable'
```

## Privacy and opt-out

Full-content tracing stores development prompts, model responses, reasoning summaries, tool
arguments, tool output, and potentially source code or credentials that appear in those values.
Use a non-sensitive test prompt first. Do not enable content capture for a session whose content
must not be retained.

For VS Code metadata-only tracing:

```jsonc
{
  "github.copilot.chat.otel.captureContent": false
}
```

To disable VS Code export entirely, set `github.copilot.chat.otel.enabled` to `false`. To disable
Codex tracing for a shell session:

```bash
export TRACE_TO_LANGFUSE=false
```

## Verify traces

1. Confirm the stack is healthy:

   ```powershell
  docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env ps --all
   ```

2. Start a new VS Code Copilot conversation and use a non-sensitive prompt that causes one simple
   tool call.
3. Start one Codex turn with a non-sensitive prompt.
4. Open `http://localhost:3000` and inspect the project traces.
5. Confirm the trace contains the agent turn, model generation, tool observation, token usage, and
   captured content expected from the selected integration.

If no traces appear, check the following in order:

- `docker compose ... ps --all`
- `docker compose ... logs --tail 200 langfuse-web`
- The VS Code process was fully restarted after setting the Windows environment variable.
- The Basic Auth value has no line wrapping or trailing newline.
- Codex has `plugin_hooks = true`, the tracing plugin is enabled, and `TRACE_TO_LANGFUSE=true`.
- The local endpoint matches `http://localhost:3000` and not a Langfuse Cloud region URL.

## Updates and maintenance

Review the coordinated Langfuse image versions in `ops/langfuse/.env.example` before upgrading.
Keep the Langfuse web and worker image releases aligned. Pull and recreate containers without
removing volumes:

```powershell
docker compose -f ops/langfuse/compose.yaml --env-file ops/langfuse/.env pull
docker compose -f ops/langfuse/compose.yaml --env-file ops/langfuse/.env up -d
```

The local deployment is intended for development observability, not high availability. It has no
remote backup, failover, or multi-host scaling. Treat the named volumes as durable local state and
back them up before Docker Desktop reinstallation or destructive maintenance.
