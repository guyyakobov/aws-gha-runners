import os
import sys
import requests

jwt_token = os.environ["JWT"]
installation_id = os.environ["INSTALLATION_ID"]

url = (
    f"https://api.github.com/app/installations/"
    f"{installation_id}/access_tokens"
)

response = requests.post(
    url,
    headers={
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
)

if not response.ok:
    print(
        f"GitHub API error: {response.status_code} {response.text}",
        file=sys.stderr,
    )
    sys.exit(1)

print(response.json()["token"])