locals {
  supported_flavors = toset(["general", "heavy"])
  default_flavor    = "general"

  common_tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}
