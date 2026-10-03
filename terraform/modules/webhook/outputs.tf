output "webhook_url" {
  description = "Public URL to be used by the GitHub App webhook endpoint"
  value       = "${aws_api_gateway_stage.webhook.invoke_url}${aws_api_gateway_resource.webhook.path}"
}
