output "webhook_url" {
  description = "Public URL to configure as the GitHub App webhook endpoint"
  value       = module.webhook.webhook_url
}
