import base64
import binascii
import hashlib
import hmac
import json
import re
from typing import Any

from .config import valid_repository_name
from .models import WorkflowJob


class PayloadError(ValueError):
    pass


def get_header(event: dict[str, Any], name: str) -> str | None:
    values = []
    for field in ("headers", "multiValueHeaders"):
        headers = event.get(field) or {}
        if not isinstance(headers, dict):
            raise PayloadError("headers must be objects")
        matches = [v for k, v in headers.items() if isinstance(k, str) and k.lower() == name.lower()]
        if len(matches) > 1:
            return None
        for value in matches:
            if field == "multiValueHeaders":
                if not isinstance(value, list) or len(value) != 1:
                    return None
                value = value[0]
            if not isinstance(value, str) or not value:
                return None
            values.append(value)
    if not values or len(set(values)) != 1:
        return None
    return values[0]


def raw_body(event: dict[str, Any]) -> bytes:
    body = event.get("body")
    encoded = event.get("isBase64Encoded", False)
    if not isinstance(body, str) or not isinstance(encoded, bool):
        raise PayloadError("body must be a string and isBase64Encoded must be a boolean")
    try:
        return base64.b64decode(body, validate=True) if encoded else body.encode("utf-8")
    except (ValueError, UnicodeError, binascii.Error):
        raise PayloadError("body encoding is invalid") from None


def valid_signature_format(signature: str | None) -> bool:
    return isinstance(signature, str) and re.fullmatch(r"sha256=[0-9a-f]{64}", signature) is not None


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not valid_signature_format(signature):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_payload(body: bytes) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError("Nonstandard JSON constant")

    try:
        payload = json.loads(body.decode("utf-8"), parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise PayloadError("body must be valid UTF-8 JSON") from None
    if not isinstance(payload, dict):
        raise PayloadError("webhook payload must be a JSON object")
    return payload


def parse_action(payload: dict[str, Any]) -> str:
    action = payload.get("action")
    if not isinstance(action, str) or not action.strip():
        raise PayloadError("action must be a nonempty string")
    return action


def parse_queued_job(payload: dict[str, Any]) -> WorkflowJob:
    def required_object(name: str) -> dict[str, Any]:
        value = payload.get(name)
        if not isinstance(value, dict):
            raise PayloadError(f"{name} must be an object")
        return value

    def positive_id(obj: dict[str, Any], key: str, path: str) -> int:
        value = obj.get(key)
        if type(value) is not int or value <= 0:
            raise PayloadError(f"{path} must be a positive integer")
        return value

    job = required_object("workflow_job")
    repo = required_object("repository")
    installation = required_object("installation")
    repository = repo.get("full_name")
    if not valid_repository_name(repository):
        raise PayloadError("repository.full_name must be an owner/repository string")
    labels = job.get("labels")
    if not isinstance(labels, list) or not all(
        isinstance(label, str) and label.strip() for label in labels
    ):
        raise PayloadError("workflow_job.labels must be an array of nonempty strings")
    return WorkflowJob(
        job_id=positive_id(job, "id", "workflow_job.id"),
        run_id=positive_id(job, "run_id", "workflow_job.run_id"),
        repository=repository,
        labels=tuple(labels),
        installation_id=positive_id(installation, "id", "installation.id"),
    )
