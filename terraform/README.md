# Deploy

Requires Terraform >= 1.12, AWS CLI credentials, Python/pip, and a runner AMI built with [Packer](../packer/README.md). Commands below use Bash / Git Bash.

## GitHub App

Create an App under **Settings -> Developer settings -> GitHub Apps**:

- Repository permissions: **Actions: Read-only**, **Administration: Read and write**.
- Subscribe to **Workflow job** events.
- Generate a private key and keep the downloaded PEM file.
- Note the **App ID** and install the App on the repository that will run jobs.

Generate a webhook secret, for example with `openssl rand -hex 32`, and save it in the App's webhook settings. Set the final webhook URL after deployment.

See GitHub's [webhook permissions](https://docs.github.com/en/webhooks/webhook-events-and-payloads#workflow_job) and [runner API permissions](https://docs.github.com/en/rest/actions/self-hosted-runners#create-configuration-for-a-just-in-time-runner-for-a-repository).

## SSM secrets

In the deployment account and region, create two **SecureString** parameters in SSM Parameter Store:

| Parameter example | Value |
| --- | --- |
| `/gha-runners/github-private-key` | Full PEM contents, including header, footer, and newlines |
| `/gha-runners/webhook-secret` | The same secret configured in the GitHub App |

Use the default SSM encryption key. Terraform references these existing parameters; it does not create them. The installation ID is read from webhook events and needs no Terraform variable.

## Lambda dependencies

Run from the repository root. Install Linux x86_64 / Python 3.12 wheels even when working on Windows:

```bash
python -m pip install -r lambdas/webhook/requirements.txt --target lambdas/webhook/package --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all:
python -m pip install -r lambdas/provisioner/requirements.txt --target lambdas/provisioner/package --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all:
```

Terraform creates the ZIP archives. Dependency folders are ignored by Git.

## Variables

Create `terraform/terraform.tfvars` using the example below. Replace the App ID and confirm the runner group ID for your setup.

```hcl
aws_region     = "us-east-1"
project_name   = "gha-runners"
vpc_cidr_block = "10.20.0.0/16"

public_subnets = {
  a = { cidr_block = "10.20.1.0/24", availability_zone = "us-east-1a" }
}
private_subnets = {
  a = { cidr_block = "10.20.11.0/24", availability_zone = "us-east-1a" }
}

runner_ami_name_prefix           = "gha-runners"
github_app_id                    = "YOUR_APP_ID"
github_runner_group_id           = 1
github_private_key_ssm_parameter = "/gha-runners/github-private-key"
webhook_secret_ssm_parameter     = "/gha-runners/webhook-secret"
jit_ssm_parameter_prefix         = "/gha-runners/jit"

general_instance_type = "t3.medium"
heavy_instance_type   = "t3.large"
max_runners           = 5
enable_waf            = true
```

Public and private subnet entries must use matching keys and availability zones. The AMI prefix must match your Packer build. Additional options are in [variables.tf](variables.tf).

Keep PEM files, secrets, local variable files, plans, and state out of Git. Terraform uses local state by default; retain it to manage or destroy the deployment.

## Apply and test

From this directory, with AWS credentials configured:

```bash
aws sts get-caller-identity
terraform init
terraform plan -out=tfplan
terraform apply tfplan
terraform output -raw webhook_url
```

Set the output URL as the GitHub App's active webhook URL, keeping SSL verification enabled. Run a workflow with `runs-on: [self-hosted, general]` or `runs-on: [self-hosted, heavy]`.

Check the App's recent deliveries, the `/aws/lambda/gha-runners-webhook` and `/aws/lambda/gha-runners-provisioner` log groups, and EC2 instances. A successful webhook delivery means the request was accepted; it does not confirm the job ran.

## Cleanup

```bash
terraform destroy
```

Separately terminate any remaining runner instances created by the provisioner. Terraform does not manage those instances, the Packer AMI/snapshots, or the two manually created SSM secrets. AWS resources, including NAT gateways, incur charges while deployed.

*For local testing with MiniStack, use the dedicated [ministack branch](../../tree/ministack). Run MiniStack with `LAMBDA_EXECUTOR=docker` to use a containerized Lambda runtime that more closely matches AWS Lambda.*
