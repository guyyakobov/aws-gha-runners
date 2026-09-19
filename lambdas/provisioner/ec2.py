from typing import Any

from .config import Config
from .models import ProvisioningRequest


class CapacityError(RuntimeError):
    pass


class FleetError(RuntimeError):
    pass


def client_token(job_id: int) -> str:
    return f"github-job-{job_id}"


def find_existing_runner(ec2: Any, request: ProvisioningRequest) -> str | None:
    pages = ec2.get_paginator("describe_instances").paginate(Filters=[
        {"Name": "tag:ManagedBy", "Values": ["gha-runners"]},
        {"Name": "tag:JobId", "Values": [str(request.job_id)]},
    ])
    for page in pages:
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
                expected = {"Repository": request.repository, "Flavor": request.flavor,
                            "JobId": str(request.job_id), "RunId": str(request.run_id)}
                if any(tags.get(key) != value for key, value in expected.items()):
                    raise FleetError("Existing runner does not match the provisioning request")
                return instance["InstanceId"]
    return None


def check_capacity(ec2: Any, maximum: int) -> None:
    pages = ec2.get_paginator("describe_instances").paginate(Filters=[
        {"Name": "tag:ManagedBy", "Values": ["gha-runners"]},
        {"Name": "instance-state-name", "Values": ["pending", "running"]},
    ])
    count = sum(len(reservation.get("Instances", []))
                for page in pages for reservation in page.get("Reservations", []))
    if count >= maximum:
        raise CapacityError(f"Runner capacity reached ({count}/{maximum})")


def create_runner(ec2: Any, config: Config, request: ProvisioningRequest, parameter_name: str) -> str:
    tags = {
        "ManagedBy": "gha-runners",
        "Repository": request.repository,
        "Flavor": request.flavor,
        "JobId": str(request.job_id),
        "RunId": str(request.run_id),
        "JIT_PARAMETER_NAME": parameter_name,
    }
    result = ec2.create_fleet(
        ClientToken=client_token(request.job_id),
        Type="instant",
        LaunchTemplateConfigs=[{
            "LaunchTemplateSpecification": {
                "LaunchTemplateId": config.launch_template_id,
                "Version": config.launch_template_version,
            },
            "Overrides": [{"InstanceType": config.instance_type(request.flavor)}],
        }],
        TargetCapacitySpecification={
            "TotalTargetCapacity": 1,
            "OnDemandTargetCapacity": 1,
            "SpotTargetCapacity": 0,
            "DefaultTargetCapacityType": "on-demand",
        },
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": key, "Value": value} for key, value in tags.items()],
        }],
    )
    instance_ids = [instance_id for group in result.get("Instances", [])
                    for instance_id in group.get("InstanceIds", [])]
    if len(instance_ids) != 1:
        raise FleetError("CreateFleet did not return exactly one runner instance")
    return instance_ids[0]
