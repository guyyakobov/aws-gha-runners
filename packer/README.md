# Runner AMI

Requires Packer, AWS credentials, and an existing public subnet with internet access and SSH access from your machine. Builds an Ubuntu 24.04 AMI with the runner, Docker, and CLI tools.

Run from this directory. Copy the example and set your VPC and subnet IDs:

```bash
cp example.pkrvars.hcl packer.pkrvars.hcl
packer init .
packer build -var-file=packer.pkrvars.hcl .
```

Use the same AWS account and region as Terraform. Set Terraform's `runner_ami_name_prefix` to the Packer `ami_name_prefix`; Terraform selects the latest matching AMI.
