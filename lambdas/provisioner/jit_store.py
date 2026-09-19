from typing import Any

from botocore.exceptions import ClientError


def read_secure_parameter(ssm: Any, name: str) -> str:
    parameter = ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]
    value = parameter.get("Value")
    if parameter.get("Type") != "SecureString" or not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a nonempty SSM SecureString")
    return value


def read_jit_config(ssm: Any, name: str) -> str | None:
    try:
        return read_secure_parameter(ssm, name)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ParameterNotFound":
            return None
        raise


def store_jit_config(ssm: Any, name: str, value: str) -> None:
    ssm.put_parameter(Name=name, Value=value, Type="SecureString",
                      Overwrite=False, Tier="Intelligent-Tiering")


def delete_jit_config(ssm: Any, name: str) -> None:
    ssm.delete_parameter(Name=name)
