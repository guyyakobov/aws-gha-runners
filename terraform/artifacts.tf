resource "aws_s3_bucket" "lambda_artifacts" {
  bucket_prefix = "${var.project_name}-lambda-artifacts-"

  tags = {
    Name = "${var.project_name}-lambda-artifacts"
  }
}