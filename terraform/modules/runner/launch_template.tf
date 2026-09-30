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