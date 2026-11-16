# NYU CTF Bench: dataset setup and safe access

This guide covers the Dataset, Docker & Evaluation module's Mốc 2A work only.
It does not run an NYU challenge, an AI agent, or an LLM API.

## Locked versions

| Item | Locked value |
| --- | --- |
| NYU CTF Bench tag | `v20250206` |
| Resolved source commit | `1dc13a0dc41a71504f727649679e2b5a6d0cb1b1` |
| NYU Python package used for setup | `nyuctf==1.1.1` |
| Python environment verified in this workspace | Python `3.12.10` |

`v20250206` is an annotated Git tag. The tag object is
`1ad3252fec94cc0c9cf3e1e5c8b3eb496a49fd57`; use the resolved source commit
above when recording an experiment.

## Safe pilot manifest

The only browser/UI-safe dataset artifact is:

```text
dataset/manifests/nyu-ctf-bench-v20250206-pilots.public.json
```

It intentionally includes only the challenge ID, name, category, public
description, and allow-listed files for these three development challenges:

- `2015q-rev-wyvern`
- `2016q-cry-sleeping_guard`
- `2016q-pwn-warmup`

It must not be supplemented with raw `challenge.json` contents. In
particular, flags, service configuration, container/image details, internal
paths, and non-allow-listed artifacts remain backend-only.

## Reproducible setup (Linux or WSL2)

The NYU package officially downloads the benchmark with a shallow Git clone.
Use a Linux filesystem in WSL2 or a Linux host; do not clone the full
repository into a native Windows NTFS worktree.

```bash
python3 -m venv .venv-dataset
. .venv-dataset/bin/activate
python -m pip install --upgrade pip
python -m pip install nyuctf==1.1.1

python -m nyuctf.download --version v20250206 --directory .ctf-data
git -C .ctf-data/v20250206 rev-parse HEAD
```

The final command must print:

```text
1dc13a0dc41a71504f727649679e2b5a6d0cb1b1
```

`.ctf-data/`, `.nyuctf/`, and `.venv-dataset/` are intentionally ignored by
Git. Keep the downloaded dataset in backend/worker storage, never in static
web assets or a browser-accessible directory.

## Access through NYU's existing loader

Do not create a second dataset loader. Once the full dataset is available,
use the NYU package and pass the checked-out index explicitly:

```python
from nyuctf.challenge import CTFChallenge
from nyuctf.dataset import CTFDataset

dataset = CTFDataset(
    dataset_json=".ctf-data/v20250206/development_dataset.json"
)
challenge = CTFChallenge(
    dataset.get("2015q-rev-wyvern"),
    dataset.basedir,
)
```

`CTFChallenge` loads private metadata in process memory. A backend adapter
must construct the public response exclusively from the allow-list used by
the pilot manifest, rather than serializing the challenge object or raw JSON.
Only files listed in `challenge.files` may be copied into an agent workspace.

## Verification result

The pinned development index contains **57** challenges:

| Category | Count |
| --- | ---: |
| crypto | 11 |
| forensics | 10 |
| misc | 6 |
| pwn | 10 |
| rev | 10 |
| web | 10 |

The NYU README and paper-era documentation describe a 55-challenge
development set. The pinned index is the source of truth for this project;
record 57 in evaluation reports and preserve the tag/commit above.

## Current Windows limitation

Mốc 2A attempted the official downloader on this Windows workspace after
confirming 69.05 GiB free on `D:`. The full clone did not finish, and a
subsequent sparse attempt was blocked by Git for Windows because the NYU
repository contains filenames that NTFS cannot check out (for example names
containing `?`). Both incomplete, ignored caches were removed.

Use WSL2/Linux for the full clone. WSL2 status is currently inaccessible to
this session, so enabling or repairing it is a host-administration task and
was not attempted here.

## Host status observed in Mốc 2A

| Check | Observed state |
| --- | --- |
| `D:` free storage after cleanup | 69.04 GiB |
| `C:` free storage before dataset work | 7.01 GiB |
| Docker client | 29.9.3 installed |
| Docker Compose | v5.7.0 installed |
| Docker Linux daemon | unavailable to this session |
| WSL2 status | access denied to this session |

`C:` does not have enough free headroom for a large Docker image cache or a
WSL virtual disk. Docker Desktop's storage location must be confirmed with
the machine owner before any Mốc 2B image pull/build. Changing that location
or repairing WSL2 is outside this repository task.

## Mốc 2B entry checklist

Do not start a challenge until all of the following are true:

1. Docker Desktop's Linux daemon and WSL2 are accessible to the worker user.
2. The full dataset is checked out at the locked commit on a Linux-compatible
   filesystem.
3. The worker can read private metadata, while the UI can read only the public
   manifest.
4. A per-run cleanup and redacted-log policy is approved.

Mốc 2B should run one service at a time: validate Compose configuration,
create the NYU-required network, start a pilot service, verify its internal
DNS/port reachability, collect redacted logs, and tear it down. Start with
`2016q-cry-sleeping_guard`, then `2016q-pwn-warmup`; do not run an LLM agent
as part of that smoke test.
