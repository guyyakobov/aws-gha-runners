resource "aws_api_gateway_rest_api" "webhook" {
  name        = "${var.project_name}-webhook"
  description = "Webhook for ${var.project_name}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Name = "${var.project_name}-webhook"
  }
}

resource "aws_api_gateway_resource" "webhook" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  parent_id   = aws_api_gateway_rest_api.webhook.root_resource_id
  path_part   = "webhook"
}

resource "aws_api_gateway_method" "webhook_post" {
  rest_api_id   = aws_api_gateway_rest_api.webhook.id
  resource_id   = aws_api_gateway_resource.webhook.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "webhook_lambda" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.webhook_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.webhook.invoke_arn
}

resource "aws_api_gateway_deployment" "webhook" {
  rest_api_id = aws_api_gateway_rest_api.webhook.id

  triggers = {
    redeployment = sha1(jsonencode({
      resource = {
        id        = aws_api_gateway_resource.webhook.id
        path_part = aws_api_gateway_resource.webhook.path_part
      }
      method = {
        id            = aws_api_gateway_method.webhook_post.id
        http_method   = aws_api_gateway_method.webhook_post.http_method
        authorization = aws_api_gateway_method.webhook_post.authorization
      }
      integration = {
        id                      = aws_api_gateway_integration.webhook_lambda.id
        http_method             = aws_api_gateway_integration.webhook_lambda.http_method
        integration_http_method = aws_api_gateway_integration.webhook_lambda.integration_http_method
        type                    = aws_api_gateway_integration.webhook_lambda.type
        uri                     = aws_api_gateway_integration.webhook_lambda.uri
      }
    }))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "webhook" {
  deployment_id = aws_api_gateway_deployment.webhook.id
  rest_api_id   = aws_api_gateway_rest_api.webhook.id
  stage_name    = "prod"

  tags = {
    Name = "${var.project_name}-webhook-prod"
  }
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.webhook.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_api_gateway_stage.webhook.execution_arn}/${aws_api_gateway_method.webhook_post.http_method}${aws_api_gateway_resource.webhook.path}"
}
