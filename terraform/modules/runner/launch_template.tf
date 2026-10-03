data "aws_ami" "runner" {
  most_recent = true
  owners      = ["self"]

  filter {
    name   = "name"
    values = ["${local.ami_name_prefix}-*"]
  }
}

resource "aws_launch_template" "runner" {
  name     = "${var.project_name}-runner"
  image_id = data.aws_ami.runner.id

  iam_instance_profile {
    arn = aws_iam_instance_profile.runner.arn
  }

  vpc_security_group_ids = [
    aws_security_group.runner.id
  ]

  metadata_options {
    http_endpoint          = "enabled"
    http_tokens            = "required"
    instance_metadata_tags = "enabled"
  }

  user_data = filebase64("${path.module}/user_data.sh")

  instance_initiated_shutdown_behavior = "terminate"

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "${var.project_name}-runner"
    }
  }

  tags = {
    Name = "${var.project_name}-runner"
  }

  depends_on = [
    aws_iam_role_policy.runner
  ]
}
