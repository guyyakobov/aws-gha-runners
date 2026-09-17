# GitHub webhook ingress (Lambda #1)

This Lambda authenticates GitHub webhooks, validates queued workflow jobs, and
publishes a small provisioning request to SQS. The directory name `webhok` follows
the requested path. There is no provisioner or infrastructure in this implementation.

## Handler and packaging

Use Python 3.12 or newer. Set the Lambda handler to:

```text
lambdas.webhok.main.lambda_handler
```

Preserve `lambdas/webhook/` relative to the deployment archive root, and install
`requirements.txt` dependencies at that root. `lambdas` is a Python namespace
package. Exclude tests, local environments, and example configuration from the
deployment archive. No AWS clients or secret reads occur during module import.

Use an API Gateway Lambda proxy integration (payload format 1.0 or 2.0).
The original request body must reach Lambda without JSON mapping templates or
other content transformations. The handler decodes base64 when
`isBase64Encoded` is true; otherwise it recovers UTF-8 bytes from `body`.
Header names are case-insensitive, and ambiguous signature headers are rejected.

## Configuration

All five variables are required; Python has no deployment-specific defaults:

| Variable | Meaning |
| --- | --- |
| `SQS_QUEUE_URL` | HTTPS URL of the destination standard SQS queue |
| `WEBHOOK_SECRET_SSM_PARAMETER` | Name or ARN of the webhook secret SecureString |
| `ALLOWED_REPOSITORIES` | JSON array of authorized exact `owner/repository` names |
| `SUPPORTED_FLAVORS` | Comma-separated, nonempty, unique supported labels |
| `DEFAULT_FLAVOR` | Flavor to use when no supported flavor label matches; must be in `SUPPORTED_FLAVORS` |

See `.env.example` for example values only. The application reads native environment
variables and does not load `.env` or depend on python-dotenv. If using shell
exports locally, quote the whole JSON array with single quotes. An empty array
`[]` intentionally authorizes no repositories. Repository and label matching are
case-sensitive; repository names should match GitHub's `repository.full_name`.

For the current setup, configure `SUPPORTED_FLAVORS=general,heavy` and
`DEFAULT_FLAVOR=general`. Neither flavor is hardcoded in the application.
The former repository-to-pool mapping is replaced by this allowlist; there is no
pool field in the queue contract. Existing Lambda configuration must supply
`ALLOWED_REPOSITORIES` and `DEFAULT_FLAVOR` when moving to this version.

Store the real GitHub webhook secret separately as an SSM `SecureString`.
On the first authenticated-format request, the Lambda calls
`get_parameter(Name=..., WithDecryption=True)` and checks the parameter type and
value. Successful retrieval is cached per parameter name for the lifetime of the
warm execution environment; failed retrieval is retried on the next invocation.
Secret rotation requires recycling warm execution environments (or changing the
configured parameter name). Configuration itself is validated each invocation.

## Request handling

1. Check the signature format, recover raw bytes, retrieve the secret, and verify
   HMAC-SHA256 using `hmac.compare_digest` before JSON parsing or event filtering.
2. Parse authenticated JSON. Only `X-GitHub-Event: workflow_job` with
   `action: queued` proceeds to required job-field validation.
3. Require positive integer job, run, and installation IDs, an `owner/repository`
   name, and an array of nonempty string labels. A missing or malformed labels
   field is a 400; an empty array is valid but cannot request a self-hosted runner.
4. Require the repository to be in `ALLOWED_REPOSITORIES` and labels to contain
   `self-hosted`. Jobs without that label are ignored, so the default does not
   cause provisioning for ordinary GitHub-hosted jobs.
5. Intersect distinct job labels with `SUPPORTED_FLAVORS`. One match selects that
   flavor; zero matches selects `DEFAULT_FLAVOR`; multiple matches are ignored
   as ambiguous. Duplicate occurrences of one flavor count as one match.
   Preserve the original labels without adding a default-flavor label.
6. Serialize the typed `ProvisioningRequest` and call SQS `SendMessage`, using
   only the configured destination URL.

| Condition | HTTP status | Sent to SQS? |
| --- | --- | --- |
| Missing, malformed, or incorrect signature | 401 | No |
| Valid unrelated event / non-queued action | 200 | No |
| Unauthorized repository | 200 | No |
| No `self-hosted` label | 200 | No |
| Multiple supported flavors | 200 | No |
| Authorized self-hosted job with no supported flavor label | 200 | Yes, using `DEFAULT_FLAVOR` |
| Malformed body, JSON, event header, or required queued-job fields | 400 | No |
| Missing/malformed configuration or SSM/internal failure | 500 | No |
| SQS failure | 500 | Delivery may be uncertain if a network error followed acceptance |
| Valid supported queued job and successful SQS send | 200 | Yes |

Signature validation requires healthy configuration and SSM; failures there return
500 when the supplied signature is syntactically valid. A malformed body encoding
returns 400 because there are no recoverable bytes to verify. Authenticated but
malformed JSON returns 400 even for unrelated events. Non-queued actions do not
require the fields used solely for provisioning.

Logs include validation reasons and job/repository/flavor context where
available. Ambiguous-flavor and default-selection logs also include labels. Secrets, signatures, full
webhook payloads, and raw exception details are never deliberately logged. Public
400/401/500 responses contain generic messages.

## SQS contract

Exactly these six fields are sent; IDs are positive JSON integers and labels are
an array of strings:

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

`flavor` is an approved configuration value. Labels remain
authenticated GitHub input; future consumers must not treat arbitrary labels as
privileged resource identifiers. This version assumes a standard queue; FIFO
message grouping/deduplication is not implemented. Webhook redeliveries and SQS
delivery can produce duplicates, so the future provisioner needs idempotency
using the job identity. This Lambda does not access a DLQ.

## Compute flavors and the shared runner configuration

There is currently one runner trust domain. `general` and `heavy` select only
compute configuration, such as instance type. The future provisioner must use
one shared runner IAM role/instance profile and one shared SSM JIT namespace for
both flavors. Those deployment settings belong to the provisioner; Lambda #1
neither selects nor sends IAM roles, instance profiles, or JIT parameter paths.

With `DEFAULT_FLAVOR=general`:

| Workflow labels | Result |
| --- | --- |
| `[self-hosted, linux]` | Queue `general` |
| `[self-hosted, linux, general]` | Queue `general` |
| `[self-hosted, linux, heavy]` | Queue `heavy` |
| `[self-hosted, general, heavy]` | Ignore ambiguous flavor request |
| `[ubuntu-latest]` | Ignore job without `self-hosted` |

Flat labels do not distinguish an unknown flavor from an unrelated custom label.
Consequently, `[self-hosted, linux, typo]` also selects the default compute flavor
and preserves `typo` in the message. This fallback does not guarantee that a runner
will match every requested label. The future provisioner must define the labels
its runners actually support.

The repository identity stays in the message, so a future version can add explicit,
configured per-team/trust-domain routing without using compute flavor as an
authorization boundary. No unused routing abstraction is introduced now.

## IAM permissions

The Lambda execution role needs:

- `ssm:GetParameter` scoped to the webhook secret parameter.
- `kms:Decrypt` on its KMS key when using a customer managed key, with a key policy
  that permits the role to decrypt.
- `sqs:SendMessage` scoped to the destination queue.
- `logs:CreateLogStream` and `logs:PutLogEvents` for its CloudWatch log group;
  `logs:CreateLogGroup` if the log group is not pre-created.
- For a queue encrypted with a customer managed KMS key, `kms:GenerateDataKey`
  and `kms:Decrypt` on that queue key, plus the corresponding key-policy access.

No GitHub API, EC2, SSM write, queue receive/delete, or DLQ permissions are needed.

## Local tests

From the repository root, with Python and pip installed:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r lambdas/webhok/requirements.txt
.venv/bin/python -m unittest discover -s lambdas/webhok/tests -v
```

Tests use standard-library `unittest` and mock every boto3 client creation. They
need no AWS credentials, deployed services, or real webhook secret. Coverage
includes authentication, byte preservation, filtering, configuration, payload
validation, the exact message contract, secret caching/retry, and safe failures.

## References

- [GitHub webhook signature validation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [API Gateway proxy payload formats](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html)
- [SSM GetParameter](https://docs.aws.amazon.com/boto3/latest/reference/services/ssm/client/get_parameter.html)
- [SQS SendMessage](https://docs.aws.amazon.com/boto3/latest/reference/services/sqs/client/send_message.html)
