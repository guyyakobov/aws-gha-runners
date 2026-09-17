import json
import logging
from typing import Any

from .config import ConfigurationError, load_config
from .github_webhook import (
    PayloadError,
    get_header,
    parse_action,
    parse_payload,
    parse_queued_job,
    raw_body,
    valid_signature_format,
    verify_signature,
)
from .secret import get_webhook_secret
from .sqs_queue import send_request
from .validator import validate_job

logger = logging.getLogger(__name__)
logging.getLogger(__package__).setLevel(logging.INFO)


def response(status_code: int, message: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": message}),
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    operation = "configuration"
    log_context: dict[str, Any] = {}
    try:
        if not isinstance(event, dict):
            raise PayloadError("proxy event must be an object")
        signature = get_header(event, "X-Hub-Signature-256")
        if not valid_signature_format(signature):
            logger.warning("Webhook authentication failed")
            return response(401, "Unauthorized")

        config = load_config()
        body = raw_body(event)
        operation = "ssm_get_parameter"
        secret = get_webhook_secret(config.secret_parameter)
        if not verify_signature(body, signature, secret):
            logger.warning("Webhook authentication failed")
            return response(401, "Unauthorized")

        operation = "payload_validation"
        payload = parse_payload(body)
        event_type = get_header(event, "X-GitHub-Event")
        if event_type is None:
            raise PayloadError("X-GitHub-Event is required and must be unambiguous")
        if event_type != "workflow_job":
            logger.info("Ignored unrelated GitHub event")
            return response(200, "Ignored")
        if parse_action(payload) != "queued":
            logger.info("Ignored non-queued workflow_job action")
            return response(200, "Ignored")

        job = parse_queued_job(payload)
        request = validate_job(job, config)
        if request is None:
            return response(200, "Ignored")

        log_context = {
            "job_id": request.job_id,
            "repository": request.repository,
            "flavor": request.flavor,
        }
        operation = "sqs_send_message"
        send_request(request, config.queue_url)
        logger.info("Provisioning request queued: %s", json.dumps(log_context))
        return response(200, "Queued")
    except PayloadError as exc:
        logger.warning("Malformed webhook: %s", exc)
        return response(400, "Malformed webhook")
    except ConfigurationError as exc:
        logger.error("Invalid Lambda configuration: %s", exc)
        return response(500, "Internal server error")
    except Exception as exc:
        logger.error(
            "Internal failure operation=%s error_type=%s context=%s",
            operation, type(exc).__name__, json.dumps(log_context),
        )
        return response(500, "Internal server error")
