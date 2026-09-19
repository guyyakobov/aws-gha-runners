import json
import re
from dataclasses import dataclass


class MessageError(ValueError):
    pass


@dataclass(frozen=True)
class ProvisioningRequest:
    job_id: int
    run_id: int
    repository: str
    flavor: str
    labels: tuple[str, ...]
    installation_id: int


def parse_request(body: str) -> ProvisioningRequest:
    def reject_constant(value: str) -> None:
        raise ValueError()

    if not isinstance(body, str):
        raise MessageError("SQS body must be a JSON string")
    try:
        data = json.loads(body, parse_constant=reject_constant)
    except (ValueError, RecursionError):
        raise MessageError("SQS body must contain valid JSON") from None
    if not isinstance(data, dict):
        raise MessageError("Provisioning request must be an object")
    for field in ("job_id", "run_id", "installation_id"):
        value = data.get(field)
        if type(value) is not int or not 0 < value < 2**63:
            raise MessageError(f"{field} must be a positive 64-bit integer")
    repository = data.get("repository")
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_-][A-Za-z0-9_-]*/[A-Za-z0-9_.-]+", repository
    ) or repository.split("/")[1] in (".", "..") or len(repository) > 256:
        raise MessageError("repository must be an owner/repository name")
    flavor = data.get("flavor")
    if flavor not in ("general", "heavy"):
        raise MessageError("Unsupported runner flavor")
    labels = data.get("labels")
    if not isinstance(labels, list) or not 1 <= len(labels) <= 100 or not all(
        isinstance(label, str) and label.strip() for label in labels
    ):
        raise MessageError("labels must contain between 1 and 100 nonempty strings")
    return ProvisioningRequest(data["job_id"], data["run_id"], repository, flavor,
                               tuple(labels), data["installation_id"])
