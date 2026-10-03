output "security_group_id" {
  value = aws_security_group.runner.id
}

output "role_arn" {
  value = aws_iam_role.runner.arn
}

output "launch_template_id" {
  value = aws_launch_template.runner.id
}

output "launch_template_version" {
  value = aws_launch_template.runner.latest_version
}