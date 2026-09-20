# Runner provisioner

Consumes the webhook Lambda's SQS messages and requests one ephemeral runner per
job:

```text
SQS → provisioner → GitHub App auth → JIT config → SSM SecureString → EC2 CreateFleet
```

The handler is `lambdas.provisioner.main.lambda_handler`, using Python 3.12. Keep
`lambdas/provisioner/` under the deployment archive root and install dependencies
there for the Lambda's Linux architecture. The webhook package is not required
in this deployment.

## Configuration

All values except the launch template version are required. Example values are
in [.env.example](.env.example); the application does not load `.env`.

| Variable | Purpose |
| --- | --- |
| `GITHUB_APP_ID` | Numeric GitHub App ID |
| `GITHUB_PRIVATE_KEY_PARAMETER` | SSM SecureString containing the PEM private key |
| `GITHUB_RUNNER_GROUP_ID` | Runner group ID required by GitHub's JIT endpoint; confirm the value for your installation |
| `RUNNER_LAUNCH_TEMPLATE_ID` | Shared runner launch template |
| `RUNNER_LAUNCH_TEMPLATE_VERSION` | Version number, `$Latest`, or `$Default`; defaults to `$Latest` |
| `RUNNER_SUBNET_IDS` | Comma-separated private subnet IDs, such as `subnet-aaa,subnet-bbb` |
| `GENERAL_INSTANCE_TYPE` | Instance type for `general` jobs |
| `HEAVY_INSTANCE_TYPE` | Instance type for `heavy` jobs |
| `MAX_RUNNERS` | Positive limit on pending and running project instances |
| `JIT_PARAMETER_PREFIX` | Shared SSM path prefix, such as `/gha-runners/jit` |

The launch template owns the AMI, instance profile, security
groups, disks, metadata settings, and bootstrap. Both flavors share the runner
role and JIT namespace. Only their instance types differ. Use a numeric launch
template version for stable retries; avoid changing deployment configuration
while jobs are being retried.

The launch template must not specify a subnet or Availability Zone, including
within network-interface settings. Placement comes from `RUNNER_SUBNET_IDS`.
Whitespace around each ID is stripped; missing values and empty entries are
rejected. Configure private subnets compatible with the template's security
groups and with the connectivity the runner needs.

Fleet receives one override per subnet, each using the selected flavor's instance
type. These are placement options for a single runner: total target capacity and
On-Demand capacity both remain **1**, regardless of the number of subnets.

## Message handling

Each `Records[].body` must contain this JSON contract:

```json
{
  "job_id": 123,
  "run_id": 456,
  "repository": "example/project",
  "flavor": "heavy",
  "labels": ["self-hosted", "heavy"],
  "installation_id": 789
}
```

The provisioner checks field types and required values, including supported
flavors and GitHub's label count limit. It does not repeat webhook authentication
or repository authorization. Only the webhook Lambda should be allowed to send
to this queue.

Authentication follows the existing [JWT script](../../github-app/generate_jwt.py)
and [installation-token script](../../github-app/generate_installation_token.py):
RS256, `iat=now-60`, `exp=now+600`, the configured App ID, and the same GitHub API
headers. The private key is read with SSM decryption. The installation ID comes
from the message. These credentials are kept in memory for that job and are
never logged.

The client posts to `/repos/{owner}/{repo}/actions/runners/generate-jitconfig`
using the installation token, the original labels, a name containing the job ID
and a UUID, the configured runner group, and `work_folder="_work"`. The GitHub App
needs repository Administration write permission for this endpoint.
[GitHub JIT API](https://docs.github.com/en/rest/actions/self-hosted-runners#create-configuration-for-a-just-in-time-runner-for-a-repository)

Before generating credentials, the provisioner checks for an existing instance
tagged `ManagedBy=gha-runners` and `JobId=<job_id>`. A matching instance is treated
as an already accepted request, even if it is stopping or terminated. Otherwise,
it counts only project instances in `pending` or `running`, across all result
pages. At or above the limit, it raises `CapacityError` so SQS can retry later.

JIT config is stored at `<JIT_PARAMETER_PREFIX>/<job_id>` with `Overwrite=False`.
An existing SecureString is reused, allowing a retry after an interrupted write
to continue without replacing credentials. `Intelligent-Tiering` lets SSM store
values above 4 KB as advanced parameters, up to its 8 KB limit; advanced
parameters incur charges. JIT parameters use the default SSM KMS key.

`CreateFleet` requests one On-Demand instance with `Type=instant` and
`ClientToken=github-job-<job_id>`. Instance tags include `ManagedBy`, `Repository`,
`Flavor`, `JobId`, `RunId`, and `JIT_PARAMETER_NAME`. Success requires one instance
ID in the fleet response; a fleet ID alone is insufficient. The handler does not
wait for the instance, runner registration, or job execution.
[Instant fleet behavior](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instant-fleet.html)

## Bootstrap handoff

The JIT value never enters user data. `ec2.py` passes only its parameter path in
the instance tag `JIT_PARAMETER_NAME`.

The future launch template must enable `MetadataOptions.InstanceMetadataTags`
and require IMDSv2. Its bootstrap must read
`/latest/meta-data/tags/instance/JIT_PARAMETER_NAME` using an IMDSv2 token, retrieve
the SecureString, delete the parameter, and start `run.sh --jitconfig` without
logging the value. That bootstrap is not implemented here. The current Packer
scripts install the runner software but do not perform this handoff.
[Instance tags in IMDS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/work-with-tags-in-IMDS.html)

## Retries and limits

Configure provisioner reserved concurrency to **1** and the SQS batch size to
**1** initially. Records are processed sequentially; a failure raises and retries
the whole batch. AWS handles polling and deletion. Configure the queue visibility
timeout and redrive policy for the Lambda timeout and expected capacity waits.

If fleet creation fails, the provisioner makes a best-effort deletion of the JIT
parameter created by that invocation, then re-raises the provisioning failure.
Cleanup failure is logged without replacing the original failure. Parameters
reused from an earlier attempt are left alone. Unexpected SDK/HTTP exceptions
are sanitized before reaching Lambda's runtime logs.

This is not an exactly-once system. EC2 visibility and client-token retention are
finite; reserved concurrency prevents overlapping handlers but does not remove
EC2's eventual consistency or other launchers. A fleet timeout can mean an
instance was accepted despite the error, and cleanup can remove its JIT parameter.
Likewise, interrupted invocations can leave expired JIT credentials or unused
GitHub runner registrations. Reconciliation and credential expiry handling are
not implemented. Do not replay old jobs as a runner-replacement mechanism.

## IAM

The provisioner execution role will need:

- `ssm:GetParameter` on the private key and JIT prefix, the latter for retry reuse.
- `ssm:PutParameter` and `ssm:DeleteParameter` on the JIT prefix.
- `ec2:DescribeInstances`, `ec2:CreateFleet`, `ec2:RunInstances`, and
  `ec2:CreateTags`, scoped where supported to the launch template, its resources,
  and the project tags.
- `iam:PassRole` on the one runner role in the launch template, restricted to
  `ec2.amazonaws.com`.
- `sqs:ReceiveMessage`, `sqs:DeleteMessage`, and `sqs:GetQueueAttributes` on the
  source queue for the Lambda event source mapping. The application does not
  call these APIs.
- CloudWatch Logs permissions: `logs:CreateLogStream`, `logs:PutLogEvents`, and
  `logs:CreateLogGroup` if the log group is not pre-created.
- `kms:Decrypt` if the private key or source queue uses a customer managed key.
  An AMI or EBS volume encrypted with a customer managed key also needs the
  corresponding EC2 KMS key-policy/grant permissions, resolved with the launch
  template during infrastructure setup.

An instant fleet does not need `AWSServiceRoleForEC2Fleet`. No template versions,
IAM roles, or instance profiles are created by this code. The separate runner
role needs SSM read/delete access to the shared JIT prefix; workflow workload
permissions belong to that role, not the provisioner.
[Fleet prerequisites](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-fleet-prerequisites.html),
[SQS event source permissions](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html)

## Tests

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r lambdas/provisioner/requirements.txt
.venv/bin/python -m unittest discover -s lambdas/provisioner/tests -v
```

Tests mock AWS and HTTP calls, verify a real RS256 signature with a temporary
test key, and validate the fleet request against boto3's service model. They need
no credentials or deployed resources.
