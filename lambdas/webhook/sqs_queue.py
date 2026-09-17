import json
from dataclasses import asdict
from functools import lru_cache
from typing import Any

import boto3

from .models import ProvisioningRequest


@lru_cache(maxsize=1)
def get_sqs_client() -> Any:
    return boto3.client("sqs")


def send_request(request: ProvisioningRequest, queue_url: str) -> None:
    get_sqs_client().send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(asdict(request), separators=(",", ":")),
    )
