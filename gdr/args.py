import argparse
from dataclasses import dataclass
import os


@dataclass
class CmdArgs:
    pipeline_url: str
    job: str
    token: str


def parse_cmd_args() -> CmdArgs:
    parser = argparse.ArgumentParser("gdr")
    parser.add_argument("-t", "--token", type=str, help="Gitlab access token")
    parser.add_argument("pipeline", type=str, help="Pipeline URL")
    parser.add_argument("job", type=str, help="Job name")

    args = parser.parse_args()

    token = os.environ["GDR_TOKEN"] if "GDR_TOKEN" in os.environ else args.token

    return CmdArgs(args.pipeline, args.job, token)
