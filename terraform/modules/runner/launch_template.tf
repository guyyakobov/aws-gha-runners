data "aws_ami" "runner" {
  most_recent = true
  owners      = ["self"]

  filter {
    name   = "name"
    values = ["${var.project_name}-runner-*"]
  }
}

resource "aws_launch_template" "runner" {
  name     = "${var.project_name}-runner"
  image_id = data.aws_ami.runner.id

  block_device_mappings {
    device_name = data.aws_ami.runner.root_device_name

    ebs {
      volume_size           = 10
      volume_size           = data.aws_ami.runner.root_device_type == "ebs" ? data.aws_ami.runner.root_device_name : 10
      encrypted             = true
      delete_on_termination = true
    }
  }

  metadata_options {
    http_endpoint          = "enabled"
    http_tokens            = "required"
    instance_metadata_tags = "enabled"
  }

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "${var.project_name}-runner"
    }
  }

  tags = {
    Name = "${var.project_name}-runner"
  }
}