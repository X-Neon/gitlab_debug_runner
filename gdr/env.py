import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

class EnvType(StrEnum):
    VAR = "env_var"
    FILE = "file"


@dataclass
class Env:
    value: str
    env_type: EnvType


def load(path: Path) -> dict[str, Env]:
    with open(path) as f:
        json_env: dict = json.load(f)

    return {k: Env(v["value"], EnvType(v["type"])) for k, v in json_env.items()}


def dump(path: Path, env_obj: dict[str, Env]) -> None:
    env_dict = {k: {"value": v.value, "type": str(v.env_type)} for k, v in env_obj.items()}

    with open(path, "w") as f:
        json.dump(env_dict, f)
