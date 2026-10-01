resource "aws_wafv2_web_acl" "webhook" {
  count = var.enable_waf ? 1 : 0

  name        = "${var.project_name}-webhook"
  description = "WAF for ${var.project_name} webhook"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-webhook-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project_name}-webhook-waf"
    sampled_requests_enabled   = true
  }

  tags = {
    Name = "${var.project_name}-webhook"
  }
}

resource "aws_wafv2_web_acl_association" "webhook" {
  count = var.enable_waf ? 1 : 0

  resource_arn = aws_api_gateway_stage.webhook.arn
  web_acl_arn  = aws_wafv2_web_acl.webhook[0].arn
}