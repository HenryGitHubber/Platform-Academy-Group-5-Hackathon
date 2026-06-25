variable "aws_region" {
  description = "AWS region to deploy all resources into"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Short project identifier used in resource names"
  type        = string
  default     = "platform-academy"
}

variable "environment" {
  description = "Deployment environment label (e.g. hackathon, dev, prod)"
  type        = string
  default     = "hackathon"
}
