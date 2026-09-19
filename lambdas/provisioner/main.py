import json
import logging
from functools import lru_cache
from typing import Any

import boto3

from .config import Config, ConfigurationError, load_config
from .ec2 import CapacityError, FleetError, check_capacity, create_runner, find_existing_runner
from .github import GitHubError, generate_app_jwt, generate_jit_config, installation_token
from .jit_store import delete_jit_config, read_jit_config, read_secure_parameter, store_jit_config
from .models import MessageError, ProvisioningRequest, parse_request

logger = logging.getLogger(__name__)
logging.getLogger(__package__).setLevel(logging.INFO)


class ProvisioningError(RuntimeError):
    pass


@lru_cache(maxsize=2)
def aws_client(service: str) -> Any:
    return boto3.client(service)


def provision_runner(request: ProvisioningRequest, config: Config, ec2: Any, ssm: Any) -> str:
    existing = find_existing_runner(ec2, request)
    if existing is not None:
        return existing
    check_capacity(ec2, config.max_runners)
    parameter_name = f"{config.jit_parameter_prefix}/{request.job_id}"
    jit_config = read_jit_config(ssm, parameter_name)
    created_parameter = False
    if jit_config is None:
        private_key = read_secure_parameter(ssm, config.github_private_key_parameter)
        app_jwt = generate_app_jwt(config.github_app_id, private_key)
        token = installation_token(app_jwt, request.installation_id)
        jit_config = generate_jit_config(request, token, config.github_runner_group_id)
        store_jit_config(ssm, parameter_name, jit_config)
        created_parameter = True
    try:
        return create_runner(ec2, config, request, parameter_name)
    except Exception:
        if created_parameter:
            try:
                delete_jit_config(ssm, parameter_name)
            except Exception as cleanup_error:
                logger.error("JIT cleanup failed job_id=%s error_type=%s",
                             request.job_id, type(cleanup_error).__name__)
        raise


def lambda_handler(event: dict[str, Any], context: Any) -> None:
    log_context: dict[str, Any] = {}
    try:
        if not isinstance(event, dict) or not isinstance(event.get("Records"), list):
            raise MessageError("SQS event must contain a Records array")
        requests = []
        for record in event["Records"]:
            if not isinstance(record, dict):
                raise MessageError("SQS record must be an object")
            requests.append(parse_request(record.get("body")))
        config = load_config()
        for request in requests:
            log_context = {"job_id": request.job_id, "repository": request.repository,
                           "flavor": request.flavor}
            instance_id = provision_runner(request, config, aws_client("ec2"), aws_client("ssm"))
            logger.info("Runner provisioned: %s", json.dumps({**log_context, "instance_id": instance_id}))
    except (MessageError, ConfigurationError, CapacityError, GitHubError, FleetError) as exc:
        logger.error("Provisioning failed reason=%s context=%s", exc, json.dumps(log_context))
        raise
    except Exception as exc:
        logger.error("Provisioning failed error_type=%s context=%s",
                     type(exc).__name__, json.dumps(log_context))
        raise ProvisioningError("Runner provisioning failed") from None
