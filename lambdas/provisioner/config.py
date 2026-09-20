import os
import re
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    github_app_id: str
    github_private_key_parameter: str
    github_runner_group_id: int
    launch_template_id: str
    launch_template_version: str
    runner_subnet_ids: tuple[str, ...]
    general_instance_type: str
    heavy_instance_type: str
    max_runners: int
    jit_parameter_prefix: str

    def instance_type(self, flavor: str) -> str:
        if flavor == "general":
            return self.general_instance_type
        if flavor == "heavy":
            return self.heavy_instance_type
        raise ConfigurationError("Unsupported runner flavor")


def load_config(environ: Mapping[str, str] | None = None) -> Config:
    environ = os.environ if environ is None else environ

    def required(name: str) -> str:
        value = environ.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"{name} is required")
        return value.strip()

    def positive_integer(name: str) -> int:
        value = required(name)
        if not re.fullmatch(r"[0-9]+", value) or int(value) <= 0:
            raise ConfigurationError(f"{name} must be a positive integer")
        return int(value)

    app_id = str(positive_integer("GITHUB_APP_ID"))
    group_id = positive_integer("GITHUB_RUNNER_GROUP_ID")
    max_runners = positive_integer("MAX_RUNNERS")
    private_key_parameter = required("GITHUB_PRIVATE_KEY_PARAMETER")
    if any(c.isspace() for c in private_key_parameter):
        raise ConfigurationError("GITHUB_PRIVATE_KEY_PARAMETER cannot contain whitespace")
    template_id = required("RUNNER_LAUNCH_TEMPLATE_ID")
    if not re.fullmatch(r"lt-[0-9a-f]+", template_id):
        raise ConfigurationError("RUNNER_LAUNCH_TEMPLATE_ID must be a launch template ID")
    version = environ.get("RUNNER_LAUNCH_TEMPLATE_VERSION", "$Latest")
    if version not in ("$Latest", "$Default") and not re.fullmatch(r"[1-9][0-9]*", version):
        raise ConfigurationError("RUNNER_LAUNCH_TEMPLATE_VERSION must be a version number, $Latest, or $Default")
    subnet_ids = tuple(subnet.strip() for subnet in required("RUNNER_SUBNET_IDS").split(","))
    if not all(subnet_ids):
        raise ConfigurationError("RUNNER_SUBNET_IDS must contain nonempty subnet IDs")
    general = required("GENERAL_INSTANCE_TYPE")
    heavy = required("HEAVY_INSTANCE_TYPE")
    for name, value in (("GENERAL_INSTANCE_TYPE", general), ("HEAVY_INSTANCE_TYPE", heavy)):
        if not re.fullmatch(r"[a-z0-9-]+\.[a-z0-9]+", value):
            raise ConfigurationError(f"{name} must be an EC2 instance type")
    prefix = required("JIT_PARAMETER_PREFIX").rstrip("/")
    if (
        not re.fullmatch(r"/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", prefix)
        or prefix.split("/")[1].lower().startswith(("aws", "ssm"))
        or len(prefix) > 180
        or prefix.count("/") >= 15
    ):
        raise ConfigurationError("JIT_PARAMETER_PREFIX must be a valid absolute SSM path up to 180 characters")
    return Config(app_id, private_key_parameter, group_id, template_id, version, subnet_ids,
                  general, heavy, max_runners, prefix)
