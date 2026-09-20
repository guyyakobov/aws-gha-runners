import json
import logging

from .config import Config
from .models import ProvisioningRequest, WorkflowJob

logger = logging.getLogger(__name__)


def validate_job(job: WorkflowJob, config: Config) -> ProvisioningRequest | None:
    context = {"job_id": job.job_id, "repository": job.repository}
    context.update(labels=job.labels)
    if "self-hosted" not in job.labels:
        logger.info("Ignored job without self-hosted label: %s", json.dumps(context))
        return None

    matches = set(job.labels) & config.supported_flavors
    if len(matches) > 1:
        logger.warning("Multiple supported flavors: %s", json.dumps(context))
        return None

    flavor = next(iter(matches)) if matches else config.default_flavor
    if not matches:
        logger.info("Using default flavor: %s", json.dumps({**context, "flavor": flavor}))

    return ProvisioningRequest(
        job_id=job.job_id,
        run_id=job.run_id,
        repository=job.repository,
        flavor=flavor,
        labels=job.labels,
        installation_id=job.installation_id,
    )
