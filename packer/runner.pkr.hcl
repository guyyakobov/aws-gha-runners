packer {
  required_plugins {
    amazon = {
      source  = "github.com/hashicorp/amazon"
      version = "~> 1"
    }
  }
}

source "amazon-ebs" "github_runner" {
  region        = var.aws_region
  instance_type = var.builder_instance_type

  vpc_id    = var.vpc_id
  subnet_id = var.subnet_id

  associate_public_ip_address = true

  ssh_username = "ubuntu"

  temporary_security_group_source_public_ip = true

  source_ami_filter {
    filters = {
      name                = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }

    owners      = ["099720109477"]
    most_recent = true
  }

  ami_name = "${var.ami_name_prefix}-{{timestamp}}"

  tags = {
    ManagedBy = "Packer"
    Purpose   = "github-actions-runner"
  }
}

build {
  name = "github-runner"

  sources = [
    "source.amazon-ebs.github_runner"
  ]

  provisioner "shell" {
    script = "${path.root}/scripts/install-tools.sh"
  }

  provisioner "shell" {
    script = "${path.root}/scripts/verify-tools.sh"
  }
}
