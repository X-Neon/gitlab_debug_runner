import docker
import docker.errors
from docker.models.volumes import Volume
from docker.models.containers import Container
from docker.models.images import Image

from pathlib import Path
from typing import cast
import sys
import os

from .job import Job

CONTAINER_NAME = "gdr-container"
VOLUME_NAME = "gdr-volume"
ENV_CONTAINER_PATH = Path("/env")


def create_shell_invocation(shell: str, commands: list[str]) -> list[str]:
    all_commands = ["set -e", "cd /build"]

    for cmd in commands:
        quote_escaped = cmd.replace("'", "'\\''")
        all_commands.append(f"echo -e '\\e[32m$ {quote_escaped}\\e[0m'")
        all_commands.append(cmd)

    return [shell, "-c", "\n".join(all_commands)]


def execute_in_docker(client: docker.DockerClient, command: list[str], image: str, variables: dict[str, str], 
                      entrypoint: str | None, file_env_path: Path) -> int:
    volumes = {
        VOLUME_NAME: {
            "bind": "/build",
            "mode": "rw"
        },
        str(file_env_path): {
            "bind": str(ENV_CONTAINER_PATH),
            "mode": "ro"
        },
    }
    container = cast(Container, client.containers.run(
        image, command, environment=variables, entrypoint=entrypoint, volumes=volumes, name=CONTAINER_NAME, detach=True))

    for line in container.logs(stream=True):
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()

    return_code = container.wait()["StatusCode"]
    container.remove(force=True)

    return return_code


def run_job(client: docker.DockerClient, job: Job, base_path: Path):
    file_env_path = base_path / "env"

    image = cast(Image, client.images.get(job.image))
    shell = cast(dict, image.attrs)["Config"]["Cmd"][0]

    print("\x1b[34mExecuting \"step_script\" stage of the job script\x1b[0m", flush=True)
    before_and_main_invocation = create_shell_invocation(shell, job.script.before + job.script.main)
    before_and_main_code = execute_in_docker(client, before_and_main_invocation, job.image, job.variables, job.entrypoint, file_env_path)

    if job.script.after:
        print("\x1b[34mRunning after_script\x1b[0m", flush=True)
        after_invocation = create_shell_invocation(shell, job.script.after)
        after_code = execute_in_docker(client, after_invocation, job.image, job.variables, job.entrypoint, file_env_path)
        if after_code:
            print(f"\x1b[33mWARNING: after_script failed: exit code {after_code}\x1b[0m", flush=True)

    if before_and_main_code:
        print(f"\x1b[31mERROR: Job failed: exit code {before_and_main_code}\x1b[0m", flush=True)
    else:
        print("\x1b[32mJob succeeded\x1b[0m", flush=True)


def create_volume(client: docker.DockerClient, base_path: Path, pipeline_base_path: Path, needs: list[str]) -> Volume:
    lower = ":".join([os.getcwd()] + [str(pipeline_base_path / n) for n in needs])
    upper = str(base_path / "run")
    work = str(base_path / "work")

    volume = client.volumes.create(VOLUME_NAME, driver="local", driver_opts={
        "device": "overlay",
        "type": "overlay",
        "o": f"lowerdir={lower},upperdir={upper},workdir={work}"
    })

    return cast(Volume, volume)


def cleanup():
    client = docker.from_env()

    try:
        container = cast(Container, client.containers.get(CONTAINER_NAME))
        container.remove(force=True)
    except docker.errors.NotFound:
        pass

    try:
        volume = cast(Volume, client.volumes.get(VOLUME_NAME))
        volume.remove(force=True)
    except docker.errors.NotFound:
        pass


def setup_and_run(job: Job, base_path: Path, pipeline_base_path: Path) -> None:
    client = docker.from_env()

    try:
        volume = create_volume(client, base_path, pipeline_base_path, job.needs)
        run_job(client, job, base_path)
        volume.remove(force=True)
    finally:
        cleanup()