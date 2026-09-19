import time
from typing import Any
from uuid import uuid4

import jwt
import requests

from .models import ProvisioningRequest


class GitHubError(RuntimeError):
    pass


def generate_app_jwt(app_id: str, private_key: str) -> str:
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + (10 * 60), "iss": app_id}
    try:
        return jwt.encode(payload, private_key, algorithm="RS256")
    except Exception:
        raise GitHubError("GitHub App JWT signing failed") from None


def post_github(path: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        with requests.post(
            f"https://api.github.com{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=payload,
            timeout=(5, 30),
            allow_redirects=False,
        ) as response:
            if response.status_code != 201:
                raise GitHubError(f"GitHub API request failed with HTTP {response.status_code}")
            result = response.json()
    except GitHubError:
        raise
    except Exception:
        raise GitHubError("GitHub API request or response failed") from None
    if not isinstance(result, dict):
        raise GitHubError("GitHub API returned an invalid response")
    return result


def installation_token(app_jwt: str, installation_id: int) -> str:
    result = post_github(f"/app/installations/{installation_id}/access_tokens", app_jwt)
    token = result.get("token")
    if not isinstance(token, str) or not token.strip():
        raise GitHubError("GitHub API response is missing the installation token")
    return token


def generate_jit_config(request: ProvisioningRequest, token: str, runner_group_id: int) -> str:
    result = post_github(
        f"/repos/{request.repository}/actions/runners/generate-jitconfig",
        token,
        {
            "name": f"github-job-{request.job_id}-{uuid4().hex}",
            "runner_group_id": runner_group_id,
            "labels": list(request.labels),
            "work_folder": "_work",
        },
    )
    value = result.get("encoded_jit_config")
    if not isinstance(value, str) or not value.strip():
        raise GitHubError("GitHub API response is missing the JIT configuration")
    return value
