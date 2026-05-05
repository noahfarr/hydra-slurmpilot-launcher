import logging
import os

import hydra
from omegaconf import DictConfig

log = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path=".", config_name="config")
def my_app(cfg: DictConfig) -> None:
    log.info(
        f"Process ID {os.getpid()} executing task {cfg.task} "
        f"(SLURM_JOB_ID={os.environ.get('SLURM_JOB_ID')}, "
        f"SLURM_ARRAY_TASK_ID={os.environ.get('SLURM_ARRAY_TASK_ID')})"
    )


if __name__ == "__main__":
    my_app()
