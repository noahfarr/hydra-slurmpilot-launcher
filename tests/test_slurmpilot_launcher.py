from hydra.core.plugins import Plugins
from hydra.plugins.launcher import Launcher

from hydra_plugins.hydra_slurmpilot_launcher.slurmpilot_launcher import (
    SlurmPilotLauncher,
)


def test_discovery() -> None:
    """The launcher class is discoverable via Hydra's plugin subsystem."""
    assert SlurmPilotLauncher.__name__ in [
        x.__name__ for x in Plugins.instance().discover(Launcher)
    ]


def test_config_registered() -> None:
    """The 'slurmpilot' launcher option is registered with the ConfigStore."""
    from hydra.core.config_store import ConfigStore

    cs = ConfigStore.instance()
    repo = cs.repo
    assert "hydra" in repo
    assert "launcher" in repo["hydra"]
    assert "slurmpilot.yaml" in repo["hydra"]["launcher"]
