from functools import lru_cache

import boto3


@lru_cache(maxsize=1)
def get_webhook_secret(parameter_name: str) -> str:
    response = boto3.client("ssm").get_parameter(Name=parameter_name, WithDecryption=True)
    parameter = response.get("Parameter", {})
    value = parameter.get("Value")
    if parameter.get("Type") != "SecureString" or not isinstance(value, str) or not value:
        raise ValueError("Webhook secret must be a nonempty SSM SecureString")
    return value
