#!/usr/bin/env bash

set -euo pipefail

IMDS="http://169.254.169.254/latest"

trap 'shutdown -h now' EXIT

# Get IMDSv2 token
IMDS_TOKEN=$(curl -fsS -X PUT \
  "${IMDS}/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")


# Get the JIT parameter name placed on this instance by the Provisioner
JIT_PARAMETER_NAME=$(curl -fsS \
  -H "X-aws-ec2-metadata-token: ${IMDS_TOKEN}" \
  "${IMDS}/meta-data/tags/instance/JIT_PARAMETER_NAME")


# Get the AWS region of this instance
AWS_REGION=$(curl -fsS \
  -H "X-aws-ec2-metadata-token: ${IMDS_TOKEN}" \
  "${IMDS}/meta-data/placement/region")


# Fetch the one-time JIT configuration from SSM
ENCODED_JIT_CONFIG=$(aws ssm get-parameter \
  --name "${JIT_PARAMETER_NAME}" \
  --with-decryption \
  --query "Parameter.Value" \
  --output text \
  --region "${AWS_REGION}")


# Delete the JIT configuration after retrieving it
aws ssm delete-parameter \
  --name "${JIT_PARAMETER_NAME}" \
  --region "${AWS_REGION}"


# Start the ephemeral GitHub Actions runner
cd /opt/actions-runner

export RUNNER_ALLOW_RUNASROOT=1

./run.sh --jitconfig "${ENCODED_JIT_CONFIG}"
