import urllib.parse
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import tempfile
import yaml
from gitlab import Gitlab

from . import args
from . import run
from . import parse
from . import gitlab_util
from . import env


@dataclass
class GitlabParams:
    instance_url: str
    instance_name: str
    project_components: list[str]
    pipeline: int


def decompose_pipeline_url(pipeline_url: str) -> GitlabParams:
    if "://" not in pipeline_url:
        # Guess protocol is HTTPS
        pipeline_url = "https://" + pipeline_url

    url = urllib.parse.urlsplit(pipeline_url)
    instance_url = f"{url.scheme}://{url.netloc}"

    # Path should have the form /group_1/.../group_N/project/[-]/pipelines/pipeline_id
    path_components = url.path[1:].split("/")
    pipeline = int(path_components[-1])

    project_components = path_components[:-2]
    if project_components[-1] == "-":
        project_components = project_components[:-1]

    return GitlabParams(instance_url, url.netloc, project_components, pipeline)


def create_paths(
    base_path: Path, instance_name: str, project_components: list[str], pipeline_id: int
):
    os.makedirs(base_path / "work", exist_ok=True)

    run_path = base_path / "run"
    if os.path.exists(run_path):
        shutil.rmtree(run_path)

    os.makedirs(run_path)

    env_path = base_path / "env"
    if os.path.exists(env_path):
        shutil.rmtree(env_path)

    os.makedirs(env_path)

    env_file = base_path / "env.json"
    if not os.path.exists(env_file):
        env.dump(env_file, {})

    instance = base_path / "instance" / instance_name
    project_path = instance.joinpath(*project_components)
    os.makedirs(project_path / "pipelines" / str(pipeline_id), exist_ok=True)


def get_base_env(
    base_path: Path, instance: str, project_components: list[str]
) -> dict[str, env.Env]:
    environ = env.load(base_path / "env.json")

    for i in range(len(project_components) + 1):
        path = (base_path / "instance" / instance).joinpath(
            *project_components[:i]
        ) / "env.json"
        environ |= env.load(path)

    return environ


def create_env_vars(environ: dict[str, env.Env], base_path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    for k, v in environ.items():
        if v.env_type == env.EnvType.FILE:
            path = base_path / "env" / k
            with open(path, "w") as f:
                f.write(v.value)

            env_vars[k] = f"/env/{k}"
        else:
            env_vars[k] = v.value

    return env_vars


def main() -> None:
    cmd_args = args.parse_cmd_args()

    gitlab_params = decompose_pipeline_url(cmd_args.pipeline_url)

    gitlab_inst = Gitlab(gitlab_params.instance_url, cmd_args.token)

    base_path = Path(tempfile.gettempdir()) / "gdr"
    create_paths(
        base_path,
        gitlab_params.instance_name,
        gitlab_params.project_components,
        gitlab_params.pipeline,
    )

    instance_path = base_path / "instance" / gitlab_params.instance_name
    gitlab_util.get_env_variables(
        gitlab_inst, gitlab_params.project_components, instance_path
    )

    with open(".gitlab-ci.yml") as f:
        ci = yaml.safe_load(f)

    job = parse.parse_ci_config(ci, cmd_args.job)

    pipeline_base_path = (
        instance_path.joinpath(*gitlab_params.project_components)
        / "pipelines"
        / str(gitlab_params.pipeline)
    )

    project_inst = gitlab_inst.projects.get("/".join(gitlab_params.project_components))
    gitlab_util.get_required_artifacts(
        project_inst, gitlab_params.pipeline, job.needs, pipeline_base_path
    )

    environ = get_base_env(
        base_path, gitlab_params.instance_name, gitlab_params.project_components
    )
    env_vars = create_env_vars(environ, base_path)
    job.variables = env_vars | job.variables

    run.setup_and_run(job, base_path, pipeline_base_path)


if __name__ == "__main__":
    main()
