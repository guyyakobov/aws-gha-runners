# GitHub webhook Lambda

Receives GitHub webhooks through API Gateway, verifies the signature, and sends
accepted runner requests to SQS. It handles queued `workflow_job` events from
allowed repositories whose jobs include the `self-hosted` label.

## Setup

Use Python 3.12 or newer with this handler:

```text
lambdas.webhook.main.lambda_handler
```

Keep `lambdas/webhook/` at the deployment archive root and install the dependencies
from `requirements.txt` at that root. Use an API Gateway proxy integration
(payload format 1.0 or 2.0) that preserves the original request body. Base64-encoded
bodies are supported.

Set all five environment variables. See [.env.example](.env.example) for examples.
The application reads environment variables directly; it does not load `.env`.

| Variable | Value |
| --- | --- |
| `SQS_QUEUE_URL` | HTTPS URL of the standard SQS queue |
| `WEBHOOK_SECRET_SSM_PARAMETER` | Name or ARN of the webhook secret in SSM |
| `ALLOWED_REPOSITORIES` | JSON array, such as `["your-org/your-repo"]` |
| `SUPPORTED_FLAVORS` | Comma-separated labels, currently `general,heavy` |
| `DEFAULT_FLAVOR` | Fallback flavor, currently `general`; must be in `SUPPORTED_FLAVORS` |

Repository names and labels are matched exactly, including case. An empty
repository array allows no repositories.

Store the webhook secret as an SSM `SecureString`. The Lambda retrieves it with
`WithDecryption=True` and caches successful reads for the lifetime of the execution
environment. After rotating the secret, replace warm environments or change the
configured parameter name.

## Flavor selection

With `SUPPORTED_FLAVORS=general,heavy` and `DEFAULT_FLAVOR=general`:

| Job labels | Result |
| --- | --- |
| `[self-hosted, linux]` | Queue `general` |
| `[self-hosted, linux, general]` | Queue `general` |
| `[self-hosted, linux, heavy]` | Queue `heavy` |
| `[self-hosted, general, heavy]` | Ignore: more than one flavor |
| `[ubuntu-latest]` | Ignore: no `self-hosted` label |

When no supported flavor matches, the default is used. This also applies to
unknown labels: `[self-hosted, typo]` selects the default and preserves `typo` in
the message. The fallback selects compute; it does not guarantee a runner will
match every requested label. Duplicate occurrences of the same flavor count once.

Both flavors use the same runner IAM role/instance profile and SSM JIT namespace.
Those shared settings and the instance-type mapping belong to the provisioner,
which is not implemented here. The repository stays in the message so per-team
configuration can be added later.

## SQS message

Only these six fields are sent. IDs are positive integers; labels are preserved
from the webhook.

```json
{
  "job_id": 123,
  "run_id": 456,
  "repository": "example/project",
  "flavor": "general",
  "labels": ["self-hosted", "linux", "general"],
  "installation_id": 789
}
```

The consumer must handle duplicate requests by job identity. A failed SQS call
returns 500, though a network failure can leave delivery uncertain. This Lambda
sends to a standard queue and does not access the DLQ.

## Responses and logs

The Lambda verifies `X-Hub-Signature-256` against the raw body using HMAC-SHA256
and a constant-time comparison before parsing JSON.

| Status | Meaning |
| --- | --- |
| `200` | Request queued, or ignored because the event, action, repository, or labels do not qualify |
| `400` | Malformed body, JSON, event header, or required job fields |
| `401` | Missing or invalid signature |
| `500` | Configuration, SSM, SQS, or other internal failure |

Malformed body encoding returns 400 before signature verification can finish.
Configuration or SSM failures return 500 when the supplied signature has a valid
format. Authenticated malformed JSON returns 400 even for unrelated events.

Logs include rejection reasons and job, repository, and flavor context. Secret
values, signatures, full payloads, and raw AWS exception messages are omitted.
Error responses contain generic messages.

## IAM permissions

The webhook Lambda execution role needs:

- `ssm:GetParameter` on the secret parameter.
- `sqs:SendMessage` on the destination queue.
- `logs:CreateLogStream` and `logs:PutLogEvents` on its log group, plus
  `logs:CreateLogGroup` if the group is not created beforehand.
- `kms:Decrypt` if the secret uses a customer managed key.
- `kms:GenerateDataKey` and `kms:Decrypt` if the queue uses a customer managed key.

Customer managed key policies must also permit that access.

## Tests

Run from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r lambdas/webhook/requirements.txt
.venv/bin/python -m unittest discover -s lambdas/webhook/tests -v
```

Tests mock AWS calls and need no credentials or deployed resources.
