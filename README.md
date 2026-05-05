# hydra-slurmpilot-launcher

A [Hydra](https://hydra.cc/) launcher plugin that submits multirun sweeps to a
Slurm cluster from your laptop via [slurmpilot](https://github.com/geoalgo/slurmpilot).

It's the same idea as [`hydra-submitit-launcher`](https://github.com/facebookresearch/hydra/tree/main/plugins/hydra_submitit_launcher),
but uses slurmpilot's SSH+rsync transport instead of submitit. That means:

- You don't need to be logged into the cluster — slurmpilot rsyncs your code
  over SSH and runs `sbatch` on your behalf.
- Jobs are *script-based*, not pickled callables, so the launcher re-invokes
  your Hydra app on the remote machine with each job's overrides as CLI args.
- Submission is fire-and-forget by default; results stay on the cluster until
  you pull them with `slurmpilot.SlurmPilot.download_job(...)` (or set
  `hydra.launcher.wait=true` to block).

## Prerequisites

1. **Passwordless SSH** to the cluster. Either an entry in `~/.ssh/config` or a
   working `ssh user@host` with key-based auth.
2. **A slurmpilot cluster config** at `~/slurmpilot/config/clusters/<name>.yaml`:

   ```yaml
   host: cluster.example.com
   user: myusername
   default_partition: gpu
   account: my-slurm-account
   remote_path: ~/slurmpilot
   ```

   See the [slurmpilot README](https://github.com/geoalgo/slurmpilot) for the
   full schema. You can skip this file if your `~/.ssh/config` already
   resolves the cluster name as a host — but then you have to set `partition`
   and `account` on the launcher itself.
3. **Python 3.12+** on both your laptop and the cluster.

## Install

```bash
pip install hydra-slurmpilot-launcher
# or, from this repo:
pip install -e .
```

## Usage

In your Hydra app's config (or on the command line), select the launcher:

```yaml
# config.yaml
defaults:
  - override hydra/launcher: slurmpilot

hydra:
  launcher:
    cluster: mycluster        # required
    partition: gpu
    n_gpus: 1
    n_cpus: 4
    mem: 16000                # MB
    max_runtime_minutes: 240
    bash_setup_command: "source ~/venv/bin/activate"
```

Run a multirun sweep:

```bash
python my_app.py --multirun lr=1e-3,1e-4 seed=0,1,2
```

That submits one Slurm array job with 6 tasks to `mycluster`. Logs land in
`~/slurmpilot/jobs/<jobname>/logs/` on the remote; pull them down with
`sp log <jobname>` or programmatically.

## Config reference

All keys live under `hydra.launcher`.

| Key | Type | Default | Notes |
|---|---|---|---|
| `cluster` | `str` | **required** | Slurmpilot cluster name |
| `jobname` | `str` | `${hydra.job.name}` | Base jobname; suffixed for uniqueness |
| `src_dir` | `str?` | cwd | Local dir uploaded to cluster |
| `entrypoint` | `str?` | `sys.argv[0]` relative to `src_dir` | The script to run |
| `python_binary` | `str?` | `"python"` | Set to `null` for bash entrypoints |
| `python_libraries` | `list[str]?` | `null` | Extra dirs to ship + add to `PYTHONPATH` |
| `bash_setup_command` | `str?` | `null` | Run before entrypoint (e.g. `conda activate`) |
| `array` | `bool` | `true` | One slurm array vs. one job per task |
| `n_concurrent_jobs` | `int?` | `null` | Throttle simultaneous array tasks |
| `wait` | `bool` | `false` | Block until each job reaches a terminal state |
| `wait_max_seconds` | `int` | `3600` | Per-job wait timeout |
| `partition` | `str?` | `null` | `--partition=` |
| `n_cpus` | `int` | `1` | `--cpus-per-task=` |
| `n_gpus` | `int?` | `null` | `--gres=gpu:N` if set |
| `mem` | `int?` | `null` | `--mem=` (MB) |
| `max_runtime_minutes` | `int` | `60` | `--time=` |
| `account` | `str?` | `null` | `--account=` |
| `env` | `dict[str,str]` | `{}` | Forwarded via `sbatch --export=ALL,K=V,...` |
| `sbatch_arguments` | `str?` | `null` | Raw extra `#SBATCH` line, e.g. `"--qos=high --nodes=2"` |
| `remote_path` | `str?` | `null` | Override cluster's default `remote_path` |

## Caveats

- **Slurmpilot ships scripts, not callables.** The launcher re-runs your
  Hydra app on the remote with the per-job overrides. Your project must be
  importable starting from `src_dir` on the cluster (or `python_libraries`
  must include any extra paths).
- **The plugin must also be installed on the cluster.** Because your
  `config.yaml` has `override hydra/launcher: slurmpilot` in its defaults
  list, the remote process needs to resolve `hydra/launcher/slurmpilot.yaml`
  too — even though it doesn't actually use the launcher (each remote run is
  a single Hydra job, not a multirun). Install
  `hydra-slurmpilot-launcher` in the cluster-side environment, or use
  `bash_setup_command` to activate a venv that has it.
- **No automatic results pull-back.** Anything your app writes lives in
  `~/slurmpilot/jobs/<jobname>/` on the remote. Use `slurmpilot.SlurmPilot.
  download_job(jobname)` or `sp` CLI to retrieve.
- **`JobReturn.return_value` is a metadata dict** (jobname, slurm_jobid,
  task_idx, cluster) rather than the user task's actual return value, since
  there's no way to recover Python return values from a remote script.
- **Jobnames must be unique** — slurmpilot raises if `~/slurmpilot/jobs/
  <jobname>/` already exists locally. The launcher appends a `coolname` +
  timestamp to avoid collisions.

## Example

The `example/` directory has a tiny Hydra app you can use to smoke-test the
plugin against the `mock` cluster (which runs jobs as local subprocesses):

```bash
cd example
python my_app.py --multirun task=1,2,3 hydra.launcher.cluster=mock
```
