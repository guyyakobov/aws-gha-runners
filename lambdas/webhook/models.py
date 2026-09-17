from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowJob:
    job_id: int
    run_id: int
    repository: str
    labels: tuple[str, ...]
    installation_id: int


@dataclass(frozen=True)
class ProvisioningRequest:
    job_id: int
    run_id: int
    repository: str
    flavor: str
    labels: tuple[str, ...]
    installation_id: int
