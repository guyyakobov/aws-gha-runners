# AWS GitHub Actions runners

Ephemeral self-hosted GitHub Actions runners on EC2. Each runner handles one job, then its instance terminates.

## Flow

GitHub webhook -> API Gateway -> webhook Lambda -> SQS -> provisioner Lambda -> EC2 runner

Packer builds the runner AMI. Terraform creates the network, queue, Lambdas, launch template, and webhook API, with optional WAF rate limiting. The provisioner uses a GitHub App to request a one-job runner configuration.

## Setup

1. [Build the runner AMI](packer/README.md).
2. [Configure the GitHub App and deploy](terraform/README.md).
3. Set the App's webhook URL to the Terraform output and run a workflow:

```yaml
runs-on: [self-hosted, general]
```

Use `heavy` instead of `general` for the larger instance type. Both types use the same AMI and IAM role.
