from dataclasses import dataclass

@dataclass
class Script:
    before: list[str]
    main: list[str]
    after: list[str]


@dataclass
class Job:
    script: Script
    image: str
    entrypoint: str | None
    variables: dict[str, str]
    needs: list[str]