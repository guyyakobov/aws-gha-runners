#!/usr/bin/env bash

set -euo pipefail

GITHUB_RUNNER_VERSION="2.337.0"
AWS_CLI_VERSION="2.36.40"
KUBECTL_VERSION="1.34.1"
HELM_VERSION="3.19.0"
ARGOCD_VERSION="3.5.3"
KUBECONFORM_VERSION="0.7.0"
YQ_VERSION="4.53.3"

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update

sudo apt-get install -y \
  ca-certificates \
  curl \
  git \
  jq \
  python3 \
  unzip

sudo curl -fsSL \
  "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_amd64" \
  -o /usr/local/bin/yq

sudo chmod +x /usr/local/bin/yq


curl -fsSL \
  "https://awscli.amazonaws.com/awscli-exe-linux-x86_64-${AWS_CLI_VERSION}.zip" \
  -o /tmp/awscliv2.zip

unzip -q /tmp/awscliv2.zip -d /tmp
sudo /tmp/aws/install


sudo curl -fsSL \
  "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
  -o /usr/local/bin/kubectl

sudo chmod +x /usr/local/bin/kubectl


curl -fsSL \
  "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz" \
  -o /tmp/helm.tar.gz

tar -xzf /tmp/helm.tar.gz -C /tmp

sudo install \
  -m 0755 \
  /tmp/linux-amd64/helm \
  /usr/local/bin/helm


sudo curl -fsSL \
  "https://github.com/argoproj/argo-cd/releases/download/v${ARGOCD_VERSION}/argocd-linux-amd64" \
  -o /usr/local/bin/argocd

sudo chmod +x /usr/local/bin/argocd


curl -fsSL \
  "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-amd64.tar.gz" \
  -o /tmp/kubeconform.tar.gz

tar -xzf /tmp/kubeconform.tar.gz -C /tmp

sudo install \
  -m 0755 \
  /tmp/kubeconform \
  /usr/local/bin/kubeconform


sudo install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo tee /etc/apt/keyrings/docker.asc > /dev/null

sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update

sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin


sudo mkdir -p /opt/actions-runner

curl -fsSL \
  "https://github.com/actions/runner/releases/download/v${GITHUB_RUNNER_VERSION}/actions-runner-linux-x64-${GITHUB_RUNNER_VERSION}.tar.gz" \
  -o /tmp/actions-runner.tar.gz

sudo tar \
  -xzf /tmp/actions-runner.tar.gz \
  -C /opt/actions-runner


sudo apt-get clean

sudo rm -rf \
  /var/lib/apt/lists/* \
  /tmp/aws \
  /tmp/awscliv2.zip \
  /tmp/helm.tar.gz \
  /tmp/linux-amd64 \
  /tmp/kubeconform.tar.gz \
  /tmp/actions-runner.tar.gz