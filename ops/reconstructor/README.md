# Linux profiling container

This Compose project runs the reconstructor under pinned Linux/amd64 CPython 3.14.6 with the
locked uv environment. It is an explicit compatibility and profiling workflow; it is not the
normal generation path and it does not include Doris, proprietary inputs, Sony SDKs, credentials,
ELF files, DWARF dumps, or generated artifacts in the image.

The image uses the exact Python digest recorded in [`images.lock.json`](images.lock.json) and copies
uv 0.12.1 from Astral's pinned image. The dependency groups required for tests, analytical-store
queries, and profiling are installed with `uv sync --frozen` into `/opt/venv`. The checkout is
mounted read-only at `/workspace`, so the image's environment remains separate from the host
checkout and every writable artifact has an explicit mount.

## Build and smoke checks

Run these commands from the repository root:

```powershell
docker compose --file ops/reconstructor/compose.yaml config --quiet
docker compose --file ops/reconstructor/compose.yaml --profile py-spy config --quiet
docker compose --file ops/reconstructor/compose.yaml build
docker compose --file ops/reconstructor/compose.yaml run --rm --entrypoint python reconstructor --version
docker compose --file ops/reconstructor/compose.yaml run --rm --entrypoint uv reconstructor --version
docker compose --file ops/reconstructor/compose.yaml run --rm reconstructor --help
docker compose --file ops/reconstructor/compose.yaml run --rm reconstructor performance doctor
```

The Compose services use the following host paths by default:

| Host path | Container path | Access | Purpose |
| --- | --- | --- | --- |
| repository root | `/workspace` | read-only | source, Git metadata, and project configuration |
| `output/` | `/workspace/output` | read-write | generated output and the durable analytical store |
| `logs/` | `/workspace/logs` | read-write | structured and human-readable application logs |
| `resources/` | `/inputs` | read-only | local fixture or explicitly selected input assets |
| `output/reconstructor-linux/` | `/artifacts` | read-write | profiler files, cache, history, and reports |

Override an input or artifact location before invoking Compose when the source lives outside the
checkout:

```powershell
$env:DDON_RECONSTRUCTOR_INPUT_DIR = 'D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21'
$env:DDON_RECONSTRUCTOR_ARTIFACT_DIR = 'C:\Temp\ddon-reconstructor-linux'
```

Set `DDON_UID` and `DDON_GID` and rebuild when using a native Linux host whose bind mounts require
a different numeric identity. Docker Desktop normally handles the Windows bind-mount permissions.

## Deterministic fixture

The fixture proves the Linux environment and artifact mounts without requiring a proprietary ELF:

```powershell
docker compose --file ops/reconstructor/compose.yaml run --rm reconstructor `
  performance benchmark `
  --iterations 1 `
  --timeout-seconds 120 `
  --artifact-dir /artifacts/profiles/fixture `
  --history-db /artifacts/history/fixture.sqlite3
```

The command writes only under `/artifacts`; it does not update the tracked
`resources/performance/benchmarks.sqlite3` ledger.

## Warm analytical-store profiling

First validate the complete source-bound manifest using the ELF mounted at `/inputs`:

```powershell
docker compose --file ops/reconstructor/compose.yaml run --rm reconstructor `
  artifacts inspect-dwarf-store `
  /workspace/output/analytical-dwarf/main/store-<source-sha16>/manifest.json `
  --source /inputs/DDOORBIS.elf
```

The manifest's source identity must match the mounted ELF. Existing Doris remains a separate
Compose project. When that service is healthy on the host, the container uses the default
`host.docker.internal` endpoints or explicit `DDON_DORIS_*` overrides.

When Docker cannot route `host.docker.internal` to the host-published ports, use the optional
`doris` profile. It attaches to the already-running `ddon-analytical-dwarf_default` network and
addresses the existing FE/BE containers by their Compose hostnames without starting or changing
Doris:

```powershell
docker compose --file ops/reconstructor/compose.yaml --profile doris config --quiet
docker compose --file ops/reconstructor/compose.yaml --profile doris run --rm reconstructor-doris `
  performance doctor
```

Run profilers independently so their overhead is not mixed:

```powershell
docker compose --file ops/reconstructor/compose.yaml --profile doris run --rm reconstructor-doris `
  performance profile-dwarf-store /inputs/DDOORBIS.elf `
  --store-manifest /workspace/output/analytical-dwarf/main/store-<source-sha16>/manifest.json `
  --output-dir /artifacts/benchmarks/linux-warm-process `
  --artifact-dir /artifacts/profiles/linux-warm-process `
  --history-db /artifacts/history/linux.sqlite3 `
  --query-existing-doris `
  --symbol rLayout --iterations 3 --profiler process-sampler
```

The same command can be repeated with `--profiler scalene`, `--profiler cprofile`, and
`--profiler pyinstrument`. A full compressed-dump index run is an explicit, long environmental
operation and must use a separately mounted `.zst` file and sidecar path.

### Scalene scope

For canonical `python -m` workloads, the Scalene adapter invokes the module wrapper with this
scope:

```text
scalene run \
  --program-path /workspace/src/ddon_dwarf_reconstructor \
  --profile-exclude scalene_target.py \
  --memory-leak-detector \
  -o /artifacts/profiles/<run>/scalene.json \
  /workspace/src/ddon_dwarf_reconstructor/infrastructure/performance/scalene_target.py \
  --module ddon_dwarf_reconstructor ...
```

The wrapper is needed because the adapter preserves a `python -m` workload under Scalene. The
package-root `--program-path` makes the whole reconstructor tree eligible while retaining
Scalene's default exclusion of the standard library and installed packages; excluding the wrapper
prevents `runpy.run_module` from becoming the apparent hotspot. The adapter does not use
Scalene's `--profile-all` by default. The repository's `performance --profiler all` option is a
separate expansion to several profiler adapters and is not this Scalene flag.

For an optional library-inclusive view, request `--profiler scalene-libraries` on the profiling
command. This is a separate diagnostic artifact that maps to `--profile-all
--profile-system-libraries` and excludes only the wrapper, so standard-library, site-package, and
application lines can be compared. It is intentionally not included in `--profiler all` because
the broad scope can dilute the application report. In current Scalene source,
`--profile-system-libraries` alone does not bypass the earlier system-path exclusion; the broad
mode must include `--profile-all`.

Every repository Scalene invocation passes `--memory-leak-detector` explicitly. Current Scalene
defaults this experimental detector on, but the explicit flag keeps the intended mode visible in
the command and evidence. Empty per-file `leaks` maps mean that the run reported no likely leaks;
they do not prove the absence of native leaks or leaks that require a longer repeated workload.

For an explicit diagnostic, the broader equivalent is:

```text
scalene run --profile-all \
  --profile-only /workspace/src/ddon_dwarf_reconstructor \
  --profile-exclude scalene_target.py ...
```

This fallback was retained as matrix evidence, but it admits system-library tracing before the
path filter and produces a larger profile. Add `--cpu-only` when only CPU line attribution is
needed; it retained the same manifest-validation hotspots in the Linux comparison while reducing
the retained JSON size. Keep the full mode when Scalene memory evidence is part of the question.

The py-spy adapter samples nonblocking at 5 Hz. This matches the default process-sampler interval
and avoids the excessive profiler CPU observed with py-spy's 100 Hz default on CPython 3.14 under
Docker Desktop/WSL2. Nonblocking sampling can report individual sampling errors; the resulting
speedscope file still retains reconstructor call frames for wall-clock localization.

For a one-time live snapshot of a running process, use py-spy's external `dump` command from the
same container or host PID namespace:

```powershell
$dump = Join-Path (Get-Location) 'output\reconstructor-linux\logs\py-spy-dump-<pid>.json'
docker compose --file ops/reconstructor/compose.yaml exec reconstructor-doris-py-spy `
  py-spy dump --pid <pid> --native --nonblocking --json `
  | Out-File -Encoding utf8 $dump
```

This complements the adapter's bounded `record` profile: `dump` captures a point-in-time stack
without restarting the target, while `record` accumulates a Speedscope profile over the whole
child run. Both remain subject to Linux ptrace permissions.

## py-spy

The py-spy service is disabled by default and grants only `SYS_PTRACE`:

```powershell
docker compose --file ops/reconstructor/compose.yaml --profile doris --profile py-spy run --rm reconstructor-doris-py-spy `
  performance profile /inputs/DDOORBIS.elf `
  --dwarf-store /workspace/output/analytical-dwarf/main/store-<source-sha16>/manifest.json `
  --symbol rLayout --state warm --profiler py-spy `
  --artifact-dir /artifacts/profiles/linux-py-spy `
  --history-db /artifacts/history/linux.sqlite3
```

Do not add `pid: host` or unrestricted seccomp as a default. If the Docker runtime still denies
process inspection, perform one explicitly labelled diagnostic run with `--security-opt
seccomp=unconfined` and record that permission requirement as environmental evidence.

## Evidence rules

Retain each run's manifest, raw profiler output, child stdout/stderr, process samples, history
database, and exported report under `/artifacts`. A Linux run is not automatically comparable with
Windows: compare only compatible source identity, workload, cold/warm state, interpreter,
configuration, and machine metadata. Scalene is actionable for line-level conclusions only when
its retained JSON contains reconstructor source-line attribution; launcher-only, process-only,
permission-failed, or missing output is recorded as partial, blocked, or unavailable. Promote an
action item only when the process sampler and at least two independent profiler surfaces agree and
output-equivalence evidence remains exact.
