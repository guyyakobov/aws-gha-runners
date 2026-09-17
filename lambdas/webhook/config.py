import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    queue_url: str
    secret_parameter: str
    allowed_repositories: frozenset[str]
    supported_flavors: frozenset[str]
    default_flavor: str


def valid_repository_name(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value
    ) is not None


def load_config(environ: Mapping[str, str] | None = None) -> Config:
    environ = os.environ if environ is None else environ

    def required(name: str) -> str:
        value = environ.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"{name} is required")
        return value.strip()

    queue_url = required("SQS_QUEUE_URL")
    try:
        url = urlsplit(queue_url)
        valid_url = (
            url.scheme == "https" and url.hostname and url.path.strip("/")
            and not url.username and not url.password and not url.query
            and not url.fragment and not any(c.isspace() for c in queue_url)
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ConfigurationError("SQS_QUEUE_URL must be an HTTPS queue URL")

    secret_parameter = required("WEBHOOK_SECRET_SSM_PARAMETER")
    if any(c.isspace() for c in secret_parameter):
        raise ConfigurationError("WEBHOOK_SECRET_SSM_PARAMETER cannot contain whitespace")

    try:
        repositories = json.loads(required("ALLOWED_REPOSITORIES"))
    except json.JSONDecodeError:
        raise ConfigurationError("ALLOWED_REPOSITORIES must be a JSON array") from None
    if not isinstance(repositories, list) or not all(
        valid_repository_name(repo) for repo in repositories
    ):
        raise ConfigurationError(
            "ALLOWED_REPOSITORIES must be a JSON array of owner/repository names"
        )

    flavors = [flavor.strip() for flavor in required("SUPPORTED_FLAVORS").split(",")]
    if not all(flavors) or len(set(flavors)) != len(flavors):
        raise ConfigurationError("SUPPORTED_FLAVORS must contain unique, nonempty labels")

    default_flavor = required("DEFAULT_FLAVOR")
    if default_flavor not in flavors:
        raise ConfigurationError("DEFAULT_FLAVOR must be listed in SUPPORTED_FLAVORS")

    return Config(
        queue_url=queue_url,
        secret_parameter=secret_parameter,
        allowed_repositories=frozenset(repositories),
        supported_flavors=frozenset(flavors),
        default_flavor=default_flavor,
    )
