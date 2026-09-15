import time
import jwt

APP_ID = "4958967"
PRIVATE_KEY_PATH = "/mnt/c/Users/Guy/Documents/aws-github-actions-runners-app.2026-09-15.private-key.pem"

with open(PRIVATE_KEY_PATH, "rb") as f:
    private_key = f.read()

now = int(time.time())

payload = {
    "iat": now - 60,
    "exp": now + (10 * 60),
    "iss": APP_ID,
}

token = jwt.encode(
    payload,
    private_key,
    algorithm="RS256"
)

print(token)