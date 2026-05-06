import logging
import os
import shlex
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from hydra.core.utils import JobReturn, JobStatus, filter_overrides
from hydra.plugins.launcher import Launcher
from hydra.types import HydraContext, TaskFunction
from omegaconf import DictConfig, OmegaConf

logger = logging.getLogger(__name__)


class SlurmPilotLauncher(Launcher):
    """Hydra launcher that submits each multirun task to a Slurm cluster
    via the `slurmpilot <https://github.com/geoalgo/slurmpilot>`_ library.

    Unlike the submitit launcher, slurmpilot ships a *script* to the cluster
    rather than a pickled callable. The launcher therefore re-invokes the
    user's Hydra application on the remote machine with the per-job overrides
    appended as CLI arguments.
    """

    def __init__(self, **params: Any) -> None:
        # Eagerly resolve any OmegaConf nodes to plain Python so slurmpilot
        # gets primitive values, not interpolations.
        self.params: dict[str, Any] = {}
        for k, v in params.items():
            if OmegaConf.is_config(v):
                v = OmegaConf.to_container(v, resolve=True)
            self.params[k] = v

        self.config: DictConfig | None = None
        self.task_function: TaskFunction | None = None
        self.hydra_context: HydraContext | None = None

    def setup(
        self,
        *,
        hydra_context: HydraContext,
        task_function: TaskFunction,
        config: DictConfig,
    ) -> None:
        self.config = config
        self.hydra_context = hydra_context
        self.task_function = task_function

    def launch(
        self, job_overrides: Sequence[Sequence[str]], initial_job_idx: int
    ) -> Sequence[JobReturn]:
        from slurmpilot import SlurmPilot, unify

        assert self.config is not None
        num_jobs = len(job_overrides)
        assert num_jobs > 0

        cluster = self.params["cluster"]
        src_dir = self._resolve_src_dir()
        entrypoint = self._resolve_entrypoint(src_dir)

        # Hydra overrides are filtered (Hydra-internal ones stripped) and then
        # quoted so values containing spaces survive the cluster-side
        # `argument=$(sed -n ...)` -> unquoted-`$argument` expansion in
        # slurmpilot's array template.
        formatted_args = [
            " ".join(shlex.quote(o) for o in filter_overrides(overrides))
            for overrides in job_overrides
        ]

        logger.info(
            f"SlurmPilot sweep: {num_jobs} job(s) -> cluster '{cluster}', "
            f"src_dir={src_dir}, entrypoint={entrypoint}"
        )
        for idx, args in enumerate(formatted_args):
            logger.info(f"\t#{initial_job_idx + idx} : {args}")

        slurm = SlurmPilot(clusters=[cluster])

        base_jobname = (
            f"{self.params['jobname']}/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        )
        if self.params["unify_method"] is not None:
            base_jobname = unify(base_jobname, method=self.params["unify_method"])

        if self.params["array"] and num_jobs > 1:
            return self._launch_array(
                slurm, base_jobname, src_dir, entrypoint, formatted_args
            )
        return self._launch_individual(
            slurm,
            base_jobname,
            src_dir,
            entrypoint,
            formatted_args,
            initial_job_idx,
        )

    def _launch_array(
        self,
        slurm: Any,
        jobname: str,
        src_dir: str,
        entrypoint: str,
        formatted_args: list[str],
    ) -> list[JobReturn]:
        from slurmpilot import JobCreationInfo

        info = JobCreationInfo(
            jobname=jobname,
            entrypoint=entrypoint,
            cluster=self.params["cluster"],
            src_dir=src_dir,
            python_binary=self.params["python_binary"],
            python_args=formatted_args,
            python_libraries=self.params["python_libraries"],
            n_concurrent_jobs=self.params["n_concurrent_jobs"],
            bash_setup_command=self.params["bash_setup_command"],
            partition=self.params["partition"],
            n_cpus=self.params["n_cpus"],
            n_gpus=self.params["n_gpus"],
            mem=self.params["mem"],
            max_runtime_minutes=self.params["max_runtime_minutes"],
            account=self.params["account"],
            env=self.params["env"] or None,
            sbatch_arguments=self.params["sbatch_arguments"],
            remote_path=self.params["remote_path"],
            ignore_patterns=self.params["ignore_patterns"],
        )
        jobid = slurm.schedule_job(info)
        logger.info(
            f"Submitted array job '{jobname}' to cluster "
            f"'{self.params['cluster']}' (slurm jobid={jobid}, "
            f"{len(formatted_args)} tasks)"
        )

        if self.params["wait"]:
            self._wait(slurm, jobname)

        return [
            self._make_return(jobname, jobid, task_idx=i)
            for i in range(len(formatted_args))
        ]

    def _launch_individual(
        self,
        slurm: Any,
        base_jobname: str,
        src_dir: str,
        entrypoint: str,
        formatted_args: list[str],
        initial_job_idx: int,
    ) -> list[JobReturn]:
        from slurmpilot import JobCreationInfo

        results: list[JobReturn] = []
        for idx, args in enumerate(formatted_args):
            real_idx = initial_job_idx + idx
            jobname = f"{base_jobname}/{real_idx}"
            info = JobCreationInfo(
                jobname=jobname,
                entrypoint=entrypoint,
                cluster=self.params["cluster"],
                src_dir=src_dir,
                python_binary=self.params["python_binary"],
                python_args=args,
                python_libraries=self.params["python_libraries"],
                bash_setup_command=self.params["bash_setup_command"],
                partition=self.params["partition"],
                n_cpus=self.params["n_cpus"],
                n_gpus=self.params["n_gpus"],
                mem=self.params["mem"],
                max_runtime_minutes=self.params["max_runtime_minutes"],
                account=self.params["account"],
                env=self.params["env"] or None,
                sbatch_arguments=self.params["sbatch_arguments"],
                remote_path=self.params["remote_path"],
                ignore_patterns=self.params["ignore_patterns"],
            )
            jobid = slurm.schedule_job(info)
            logger.info(
                f"Submitted '{jobname}' to cluster '{self.params['cluster']}' "
                f"(slurm jobid={jobid})"
            )
            if self.params["wait"]:
                self._wait(slurm, jobname)
            results.append(self._make_return(jobname, jobid))
        return results

    def _resolve_src_dir(self) -> str:
        src_dir = self.params.get("src_dir") or os.getcwd()
        return str(Path(src_dir).resolve())

    def _resolve_entrypoint(self, src_dir: str) -> str:
        entrypoint = self.params.get("entrypoint")
        if entrypoint:
            return entrypoint
        argv0 = Path(sys.argv[0]).resolve()
        try:
            return str(argv0.relative_to(Path(src_dir)))
        except ValueError as e:
            raise ValueError(
                f"Could not infer entrypoint: sys.argv[0]={argv0} is not under "
                f"src_dir={src_dir}. Set hydra.launcher.entrypoint explicitly."
            ) from e

    def _wait(self, slurm: Any, jobname: str) -> None:
        state = slurm.wait_completion(
            jobname=jobname, max_seconds=self.params["wait_max_seconds"]
        )
        logger.info(f"Job '{jobname}' finished with state={state}")

    def _make_return(
        self, jobname: str, jobid: int | None, task_idx: int | None = None
    ) -> JobReturn:
        # Submission was successful — the job is now slurm's responsibility.
        # We can't recover the user task's actual return value from a remote
        # script, so return_value is metadata about the submission.
        ret = JobReturn()
        ret.status = JobStatus.COMPLETED
        ret.return_value = {
            "jobname": jobname,
            "slurm_jobid": jobid,
            "task_idx": task_idx,
            "cluster": self.params["cluster"],
        }
        return ret
