from .job import Job, Script
from typing import cast


def merge_jobs(base: dict, update: dict):
    for k, v in update.items():
        if k == "extends":
            continue

        if isinstance(v, dict):
            if k not in base:
                base[k] = {}

            base[k].update(v)
        else:
            base[k] = v


def normalise_ci_job(ci: dict, ci_job: dict, top_level: bool = False) -> dict:
    if "extends" not in ci_job:
        return ci_job

    new_job = {}

    if "extends" not in ci_job:
        extends = []
    elif isinstance(ci_job["extends"], str):
        extends = [ci_job["extends"]]
    else:
        extends = cast(list[str], ci_job["extends"])

    if top_level and "default" in ci:
        extends = ["default"] + extends

    if top_level and "variables" in ci:
        new_job["variables"] = ci["variables"]

    for e in extends:
        e_norm = normalise_ci_job(ci, ci[e])
        merge_jobs(new_job, e_norm)

    merge_jobs(new_job, ci_job)
    return new_job


def parse_ci_config(ci: dict, job_name: str) -> Job:
    ci_job = ci[job_name] 
    norm_job = normalise_ci_job(ci, ci_job, top_level=True)

    before_script = norm_job["before_script"] if "before_script" in norm_job else []
    script = norm_job["script"]
    image = norm_job["image"]
    after_script = norm_job["after_script"] if "after_script" in norm_job else []
    entrypoint = norm_job["image"]["entrypoint"] if "entrypoint" in norm_job["image"] else None
    variables = norm_job["variables"] if "variables" in norm_job else {}
    needs = norm_job["needs"] if "needs" in norm_job else []

    if "needs" not in norm_job:
        needs = []
    elif isinstance(norm_job["needs"], str):
        needs = [norm_job["needs"]]
    else:
        needs = norm_job["needs"]

    return Job(Script(before_script, script, after_script), image, entrypoint, variables, needs)