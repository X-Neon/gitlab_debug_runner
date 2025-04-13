from pathlib import Path
from gitlab import Gitlab
from gitlab.v4.objects import Project
import os
from io import BytesIO
from zipfile import ZipFile

from . import env


def convert_rest_env_obj(env_obj) -> env.Env:
    e = env_obj.attributes
    return env.Env(
        e["value"],
        env.EnvType.FILE if e["variable_type"] == "file" else env.EnvType.VAR,
    )


def write_env_file(path: Path, rest_env_list) -> None:
    env_transformed = {
        str(e.attributes["key"]): convert_rest_env_obj(e) for e in rest_env_list
    }
    env.dump(path, env_transformed)


def get_env_variables(
    gitlab_inst: Gitlab, project_components: list[str], inst_base_path: Path
) -> None:
    if not os.path.exists(inst_base_path / "env.json"):
        write_env_file(
            inst_base_path / "env.json", gitlab_inst.variables.list(get_all=True)
        )

    for i in range(1, len(project_components)):
        group = "/".join(project_components[:i])
        group_path = inst_base_path.joinpath(*project_components[:i])

        if not os.path.exists(group_path / "env.json"):
            write_env_file(
                group_path / "env.json",
                gitlab_inst.groups.get(group).variables.list(get_all=True),
            )

    project_path = inst_base_path.joinpath(*project_components)
    if not os.path.exists(project_path / "env.json"):
        write_env_file(
            project_path / "env.json",
            gitlab_inst.projects.get("/".join(project_components)).variables.list(
                get_all=True
            ),
        )


def download_artifacts(
    project_inst: Project, pipeline_id: int, jobs: list[str], pipeline_base_path: Path
) -> None:
    pipeline = project_inst.pipelines.get(pipeline_id)

    for j in pipeline.jobs.list(get_all=True):
        if j.attributes["name"] not in jobs:
            continue

        extract_path = pipeline_base_path / j.attributes["name"]
        os.makedirs(extract_path, exist_ok=False)

        project_job = project_inst.jobs.get(j.id)

        artifact_data = BytesIO(project_job.artifacts())
        with ZipFile(artifact_data) as z:
            z.extractall(extract_path)


def get_required_artifacts(
    project_inst: Project, pipeline_id: int, jobs: list[str], pipeline_base_path: Path
) -> None:
    download_jobs = [j for j in jobs if not os.path.exists(pipeline_base_path / j)]

    if not download_jobs:
        return

    download_artifacts(project_inst, pipeline_id, jobs, pipeline_base_path)
