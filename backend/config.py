from pathlib import Path

import yaml

# the project folder, worked out from where this file lives, so paths work
# no matter which folder the app is started from
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "configs" / "config.yaml"


def load_config(path=CONFIG_PATH):
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    return config
