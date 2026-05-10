from dataclasses import dataclass, field

from hydra.core.config_store import ConfigStore
from omegaconf import MISSING


@dataclass
class SlurmPilotQueueConf:
    """Configuration for the slurmpilot Hydra launcher.

    Mirrors ``slurmpilot.JobCreationInfo`` for the per-job slurm fields, plus
    a few launcher-level options that control how a multirun maps onto
    slurmpilot submissions.
    """

    _target_: str = (
        "hydra_plugins.hydra_slurmpilot_launcher.slurmpilot_launcher.SlurmPilotLauncher"
    )

    # Cluster name as known to slurmpilot. Must match either an entry in
    # ~/slurmpilot/config/clusters/<name>.yaml, a hostname resolvable via
    # ~/.ssh/config, or one of the special values "mock" / "local".
    cluster: str = MISSING

    # Base jobname. A `YYYY-MM-DD_HH-MM-SS` timestamp is always appended for
    # uniqueness; `unify_method` controls whether anything else is added.
    jobname: str = "${hydra.job.name}"

    # Extra suffix appended after the timestamp to disambiguate sweeps that
    # land in the same second. One of:
    #   - null      no extra suffix; the timestamp alone must be unique
    #   - "ascii"   random 5-char alphanumeric (e.g. "A3K9P")
    #   - "coolname" 4-word slug (e.g. "fervent-enlightened-mule-of-fragrance")
    #   - "date"    a second timestamp (redundant; included for completeness)
    unify_method: str | None = None

    # Local source directory uploaded to the cluster.
    # null -> current working directory at launch time.
    src_dir: str | None = None

    # Entrypoint path relative to src_dir. null -> inferred from sys.argv[0].
    entrypoint: str | None = None

    # Python interpreter on the cluster. Set to null to run the entrypoint
    # via bash instead.
    python_binary: str | None = "python"

    # Extra local directories shipped to the cluster and added to PYTHONPATH.
    python_libraries: list[str] | None = None

    # Shell command run before the entrypoint (e.g. "source ~/venv/bin/activate").
    bash_setup_command: str | None = None

    # If True, submit a single slurm array job covering every multirun task.
    # If False, submit one slurm job per task.
    array: bool = True

    # Max simultaneous array tasks (only when array=True).
    n_concurrent_jobs: int | None = None

    # Block until each submitted job reaches a terminal state.
    wait: bool = False

    # Per-job timeout when wait=True (seconds).
    wait_max_seconds: int = 3600

    # Slurm resource fields (mapped 1:1 onto slurmpilot.JobCreationInfo).
    partition: str | None = None
    n_cpus: int = 1
    n_gpus: int | None = None
    mem: int | None = None  # Memory in MB.
    max_runtime_minutes: int = 60
    account: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    # Raw extra sbatch flags as a single string, e.g. "--qos=high --nodes=2".
    sbatch_arguments: str | None = None
    # Override the cluster's default remote_path.
    remote_path: str | None = None


ConfigStore.instance().store(
    group="hydra/launcher",
    name="slurmpilot",
    node=SlurmPilotQueueConf(),
    provider="slurmpilot_launcher",
)
