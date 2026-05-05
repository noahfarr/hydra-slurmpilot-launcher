from dataclasses import dataclass, field
from typing import Dict, List, Optional

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

    # Base jobname; each multirun job gets a unique suffix appended.
    jobname: str = "${hydra.job.name}"

    # Local source directory uploaded to the cluster.
    # null -> current working directory at launch time.
    src_dir: Optional[str] = None

    # Entrypoint path relative to src_dir. null -> inferred from sys.argv[0].
    entrypoint: Optional[str] = None

    # Python interpreter on the cluster. Set to null to run the entrypoint
    # via bash instead.
    python_binary: Optional[str] = "python"

    # Extra local directories shipped to the cluster and added to PYTHONPATH.
    python_libraries: Optional[List[str]] = None

    # Shell command run before the entrypoint (e.g. "source ~/venv/bin/activate").
    bash_setup_command: Optional[str] = None

    # If True, submit a single slurm array job covering every multirun task.
    # If False, submit one slurm job per task.
    array: bool = True

    # Max simultaneous array tasks (only when array=True).
    n_concurrent_jobs: Optional[int] = None

    # Block until each submitted job reaches a terminal state.
    wait: bool = False

    # Per-job timeout when wait=True (seconds).
    wait_max_seconds: int = 3600

    # Slurm resource fields (mapped 1:1 onto slurmpilot.JobCreationInfo).
    partition: Optional[str] = None
    n_cpus: int = 1
    n_gpus: Optional[int] = None
    mem: Optional[int] = None  # MB
    max_runtime_minutes: int = 60
    account: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    # Raw extra sbatch flags as a single string, e.g. "--qos=high --nodes=2".
    sbatch_arguments: Optional[str] = None
    # Override the cluster's default remote_path.
    remote_path: Optional[str] = None


ConfigStore.instance().store(
    group="hydra/launcher",
    name="slurmpilot",
    node=SlurmPilotQueueConf(),
    provider="slurmpilot_launcher",
)
