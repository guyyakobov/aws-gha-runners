import base64
import copy
import hashlib
import hmac
import json
import unittest
from dataclasses import asdict
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from lambdas.webhook import main
from lambdas.webhook.config import ConfigurationError, load_config
from lambdas.webhook.github_webhook import verify_signature
from lambdas.webhook.secret import get_webhook_secret
from lambdas.webhook.sqs_queue import get_sqs_client


SECRET = "test-only-webhook-secret"
ENV = {
    "SQS_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/123456789012/test-jobs",
    "WEBHOOK_SECRET_SSM_PARAMETER": "/tests/webhook-secret",
    "SUPPORTED_FLAVORS": "general,heavy",
    "DEFAULT_FLAVOR": "general",
}
PAYLOAD = {
    "action": "queued",
    "workflow_job": {
        "id": 123,
        "run_id": 456,
        "labels": ["self-hosted", "linux", "general"],
        "unneeded_field": "must not be forwarded",
    },
    "repository": {"full_name": "example/project"},
    "installation": {"id": 789},
    "sender": {"login": "not-forwarded"},
}
EXPECTED_MESSAGE = {
    "job_id": 123,
    "run_id": 456,
    "repository": "example/project",
    "flavor": "general",
    "labels": ["self-hosted", "linux", "general"],
    "installation_id": 789,
}


def signed_event(payload=None, *, raw=None, encoded=False, event_type="workflow_job"):
    body = json.dumps(PAYLOAD if payload is None else payload).encode() if raw is None else raw
    signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {
        "headers": {"X-Hub-Signature-256": signature, "X-GitHub-Event": event_type},
        "body": base64.b64encode(body).decode() if encoded else body.decode(),
        "isBase64Encoded": encoded,
    }


class SignatureTests(unittest.TestCase):
    def test_github_published_hmac_vector(self):
        self.assertTrue(verify_signature(
            b"Hello, World!",
            "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17",
            "It's a Secret to Everybody",
        ))

    def test_invalid_and_missing_signatures(self):
        for signature in (None, "", "sha256=" + "0" * 64, "sha1=bad", "sha256=\u00e9"):
            with self.subTest(signature=signature):
                self.assertFalse(verify_signature(b"body", signature, SECRET))

    def test_uses_constant_time_comparison(self):
        with patch("lambdas.webhook.github_webhook.hmac.compare_digest", return_value=True) as compare:
            self.assertTrue(verify_signature(b"body", "sha256=" + "0" * 64, SECRET))
        compare.assert_called_once()


class ConfigTests(unittest.TestCase):
    def test_valid_configuration(self):
        config = load_config(ENV)
        self.assertEqual(config.queue_url, ENV["SQS_QUEUE_URL"])
        self.assertEqual(config.secret_parameter, ENV["WEBHOOK_SECRET_SSM_PARAMETER"])
        self.assertEqual(config.supported_flavors, frozenset({"general", "heavy"}))
        self.assertEqual(config.default_flavor, "general")

    def test_missing_required_configuration(self):
        for key in ENV:
            for value in (None, "", "   "):
                with self.subTest(key=key, value=value):
                    env = dict(ENV)
                    if value is None:
                        del env[key]
                    else:
                        env[key] = value
                    with self.assertRaisesRegex(ConfigurationError, key):
                        load_config(env)

    def test_default_flavor_must_be_supported(self):
        for flavor in ("unknown", "general,heavy"):
            with self.subTest(flavor=flavor):
                with self.assertRaisesRegex(ConfigurationError, "DEFAULT_FLAVOR"):
                    load_config({**ENV, "DEFAULT_FLAVOR": flavor})

    def test_invalid_flavor_configuration(self):
        for value in (",", "general,", "general,,heavy", "general,general"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ConfigurationError, "SUPPORTED_FLAVORS"):
                    load_config({**ENV, "SUPPORTED_FLAVORS": value})

    def test_invalid_queue_url_and_parameter(self):
        for key, value in (
            ("SQS_QUEUE_URL", "not-a-url"),
            ("SQS_QUEUE_URL", "http://example.com/queue"),
            ("SQS_QUEUE_URL", "https://example.com"),
            ("SQS_QUEUE_URL", "https://[invalid/queue"),
            ("WEBHOOK_SECRET_SSM_PARAMETER", "invalid parameter"),
        ):
            with self.subTest(key=key, value=value):
                with self.assertRaisesRegex(ConfigurationError, key):
                    load_config({**ENV, key: value})


class HandlerTests(unittest.TestCase):
    def setUp(self):
        get_webhook_secret.cache_clear()
        get_sqs_client.cache_clear()
        self.addCleanup(get_webhook_secret.cache_clear)
        self.addCleanup(get_sqs_client.cache_clear)
        self.env = patch.dict("os.environ", ENV, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.ssm = Mock()
        self.ssm.get_parameter.return_value = {
            "Parameter": {"Type": "SecureString", "Value": SECRET}
        }
        self.sqs = Mock()
        self.sqs.send_message.return_value = {"MessageId": "test-message-id"}
        clients = patch("boto3.client", side_effect={"ssm": self.ssm, "sqs": self.sqs}.__getitem__)
        self.clients = clients.start()
        self.addCleanup(clients.stop)

    def assert_status(self, event, status):
        result = main.lambda_handler(event, None)
        self.assertEqual(result["statusCode"], status, result)
        self.assertEqual(result["headers"]["Content-Type"], "application/json")
        return result

    def assert_not_queued(self, event, status=200):
        result = self.assert_status(event, status)
        self.sqs.send_message.assert_not_called()
        return result

    def test_queued_job_and_exact_sqs_json_body(self):
        result = self.assert_status(signed_event(), 200)
        self.assertEqual(json.loads(result["body"]), {"message": "Queued"})
        self.ssm.get_parameter.assert_called_once_with(
            Name=ENV["WEBHOOK_SECRET_SSM_PARAMETER"], WithDecryption=True
        )
        self.sqs.send_message.assert_called_once()
        kwargs = self.sqs.send_message.call_args.kwargs
        self.assertEqual(set(kwargs), {"QueueUrl", "MessageBody"})
        self.assertEqual(kwargs["QueueUrl"], ENV["SQS_QUEUE_URL"])
        self.assertEqual(json.loads(kwargs["MessageBody"]), EXPECTED_MESSAGE)

    def test_typed_provisioning_request(self):
        with patch("lambdas.webhook.main.send_request") as send:
            self.assert_status(signed_event(), 200)
        request, queue_url = send.call_args.args
        self.assertEqual(type(request).__name__, "ProvisioningRequest")
        self.assertEqual(json.loads(json.dumps(asdict(request))), EXPECTED_MESSAGE)
        self.assertEqual(queue_url, ENV["SQS_QUEUE_URL"])

    def test_invalid_signature(self):
        event = signed_event()
        event["headers"]["X-Hub-Signature-256"] = "sha256=" + "0" * 64
        self.assert_not_queued(event, 401)

    def test_missing_or_malformed_signature(self):
        for signature in (None, "", "sha1=bad", "sha256=\u00e9", 123):
            with self.subTest(signature=signature):
                event = signed_event()
                event["headers"]["X-Hub-Signature-256"] = signature
                self.assert_not_queued(event, 401)
        self.ssm.get_parameter.assert_not_called()

    def test_authentication_precedes_json_parsing_and_event_filtering(self):
        event = signed_event(raw=b"not json", event_type="ping")
        event["headers"]["X-Hub-Signature-256"] = "sha256=" + "0" * 64
        self.assert_not_queued(event, 401)

    def test_signature_covers_exact_body_including_whitespace(self):
        event = signed_event()
        event["body"] += " "
        self.assert_not_queued(event, 401)

    def test_base64_body_unicode_and_whitespace(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["workflow_job"]["labels"].append("caf\u00e9")
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode() + b"\n"
        self.assert_status(signed_event(raw=raw, encoded=True), 200)
        message = json.loads(self.sqs.send_message.call_args.kwargs["MessageBody"])
        self.assertEqual(message["labels"][-1], "caf\u00e9")

    def test_case_insensitive_headers_and_payload_versions(self):
        for version in ("1.0", "2.0"):
            with self.subTest(version=version):
                event = signed_event()
                event["version"] = version
                event["headers"] = {key.lower(): value for key, value in event["headers"].items()}
                self.assert_status(event, 200)

    def test_single_value_proxy_multivalue_headers(self):
        event = signed_event()
        event["multiValueHeaders"] = {key: [value] for key, value in event["headers"].items()}
        event["headers"] = None
        self.assert_status(event, 200)

    def test_duplicate_signature_headers_fail_closed(self):
        event = signed_event()
        signature = event["headers"]["X-Hub-Signature-256"]
        event["multiValueHeaders"] = {"X-Hub-Signature-256": [signature, signature]}
        self.assert_not_queued(event, 401)

    def test_ignored_unrelated_event(self):
        self.assert_not_queued(signed_event({"zen": "test"}, event_type="ping"))

    def test_ignored_nonqueued_action(self):
        for action in ("completed", "in_progress", "waiting"):
            with self.subTest(action=action):
                self.assert_not_queued(signed_event({"action": action}))

    def test_repositories_and_installations_from_authenticated_payload_are_forwarded(self):
        for repository, installation_id in (("example/another-project", 987),
                                            ("another-org/repository", 654)):
            with self.subTest(repository=repository, installation_id=installation_id):
                payload = copy.deepcopy(PAYLOAD)
                payload["repository"]["full_name"] = repository
                payload["installation"]["id"] = installation_id
                result = self.assert_status(signed_event(payload), 200)
                self.assertEqual(json.loads(result["body"]), {"message": "Queued"})
                message = json.loads(self.sqs.send_message.call_args.kwargs["MessageBody"])
                self.assertEqual(message, {**EXPECTED_MESSAGE, "repository": repository,
                                          "installation_id": installation_id})

    def test_default_flavor_for_another_repository(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["repository"]["full_name"] = "another-org/repository"
        payload["workflow_job"]["labels"] = ["self-hosted", "linux"]
        self.assert_status(signed_event(payload), 200)
        message = json.loads(self.sqs.send_message.call_args.kwargs["MessageBody"])
        self.assertEqual(message, {**EXPECTED_MESSAGE, "repository": "another-org/repository",
                                  "labels": ["self-hosted", "linux"]})

    def test_general_and_heavy_flavors(self):
        for flavor in ("general", "heavy"):
            with self.subTest(flavor=flavor):
                payload = copy.deepcopy(PAYLOAD)
                payload["workflow_job"]["labels"] = ["self-hosted", "linux", flavor]
                self.assert_status(signed_event(payload), 200)
                message = json.loads(self.sqs.send_message.call_args.kwargs["MessageBody"])
                self.assertEqual(message["flavor"], flavor)
                self.assertEqual(message, {**EXPECTED_MESSAGE, "flavor": flavor,
                                           "labels": ["self-hosted", "linux", flavor]})

    def test_custom_configuration_controls_flavor(self):
        with patch.dict("os.environ", {
            "SUPPORTED_FLAVORS": "gpu",
            "DEFAULT_FLAVOR": "gpu",
        }):
            payload = copy.deepcopy(PAYLOAD)
            payload["repository"]["full_name"] = "example/another-project"
            payload["workflow_job"]["labels"] = ["self-hosted", "gpu"]
            self.assert_status(signed_event(payload), 200)
        message = json.loads(self.sqs.send_message.call_args.kwargs["MessageBody"])
        self.assertEqual(message["repository"], "example/another-project")
        self.assertEqual(message["flavor"], "gpu")

    def test_no_supported_flavor_uses_default_and_preserves_labels(self):
        for labels in (["self-hosted"], ["self-hosted", "linux"], ["self-hosted", "unsupported"]):
            with self.subTest(labels=labels):
                payload = copy.deepcopy(PAYLOAD)
                payload["workflow_job"]["labels"] = labels
                with self.assertLogs("lambdas.webhook", level="INFO") as logs:
                    self.assert_status(signed_event(payload), 200)
                message = json.loads(self.sqs.send_message.call_args.kwargs["MessageBody"])
                self.assertEqual(message, {**EXPECTED_MESSAGE, "labels": labels})
                self.assertIn("Using default flavor", " ".join(logs.output))

    def test_default_can_be_heavy_and_explicit_flavor_overrides_it(self):
        with patch.dict("os.environ", {"DEFAULT_FLAVOR": "heavy"}):
            for labels, expected in ((["self-hosted", "linux"], "heavy"),
                                     (["self-hosted", "general"], "general")):
                with self.subTest(labels=labels):
                    payload = copy.deepcopy(PAYLOAD)
                    payload["workflow_job"]["labels"] = labels
                    self.assert_status(signed_event(payload), 200)
                    message = json.loads(self.sqs.send_message.call_args.kwargs["MessageBody"])
                    self.assertEqual(message["flavor"], expected)

    def test_jobs_without_self_hosted_label_are_ignored(self):
        for labels in ([], ["ubuntu-latest"], ["general"], ["heavy"]):
            with self.subTest(labels=labels):
                payload = copy.deepcopy(PAYLOAD)
                payload["workflow_job"]["labels"] = labels
                self.assert_not_queued(signed_event(payload))

    def test_invalid_default_configuration_cannot_publish(self):
        with patch.dict("os.environ", {"DEFAULT_FLAVOR": "unknown"}):
            self.assert_not_queued(signed_event(), 500)
        self.ssm.get_parameter.assert_not_called()

    def test_multiple_supported_flavors(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["workflow_job"]["labels"] = ["self-hosted", "general", "heavy"]
        with self.assertLogs("lambdas.webhook", level="WARNING") as logs:
            self.assert_not_queued(signed_event(payload))
        self.assertIn("Multiple supported flavors", " ".join(logs.output))

    def test_repeated_same_flavor_is_one_distinct_match(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["workflow_job"]["labels"] = ["self-hosted", "general", "general"]
        self.assert_status(signed_event(payload), 200)

    def test_malformed_json_and_nonobject_payload(self):
        for body in (b"{", b"[]", b"null", b'{"number":NaN}', b"\xff"):
            with self.subTest(body=body):
                self.assert_not_queued(signed_event(raw=body, encoded=True), 400)

    def test_malformed_required_payload_fields(self):
        cases = [
            ("action", None), ("action", 1), ("action", ""),
            ("workflow_job", None), ("repository", []), ("installation", None),
            ("workflow_job.id", None), ("workflow_job.id", True),
            ("workflow_job.id", "123"), ("workflow_job.id", 0),
            ("workflow_job.run_id", -1), ("workflow_job.run_id", 1.5),
            ("repository.full_name", "invalid"), ("repository.full_name", 123),
            ("workflow_job.labels", None), ("workflow_job.labels", "general"),
            ("workflow_job.labels", ["general", 1]), ("workflow_job.labels", [""]),
            ("installation.id", False), ("installation.id", None),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                payload = copy.deepcopy(PAYLOAD)
                parent = payload
                keys = path.split(".")
                for key in keys[:-1]:
                    parent = parent[key]
                parent[keys[-1]] = value
                self.assert_not_queued(signed_event(payload), 400)

    def test_missing_required_payload_fields(self):
        for key in ("action", "workflow_job", "repository", "installation"):
            with self.subTest(key=key):
                payload = copy.deepcopy(PAYLOAD)
                del payload[key]
                self.assert_not_queued(signed_event(payload), 400)

    def test_malformed_proxy_body(self):
        for body, encoded in ((None, False), ({}, False), ("%%", True), ("body", "true")):
            with self.subTest(body=body, encoded=encoded):
                event = signed_event()
                event.update(body=body, isBase64Encoded=encoded)
                self.assert_not_queued(event, 400)

    def test_missing_event_header(self):
        event = signed_event()
        del event["headers"]["X-GitHub-Event"]
        self.assert_not_queued(event, 400)

    def test_configuration_failure_is_generic_server_error(self):
        with patch.dict("os.environ", {"SQS_QUEUE_URL": "invalid"}):
            result = self.assert_not_queued(signed_event(), 500)
        self.assertEqual(json.loads(result["body"]), {"message": "Internal server error"})
        self.ssm.get_parameter.assert_not_called()

    def test_secret_is_cached_for_warm_invocations(self):
        self.assert_status(signed_event(), 200)
        self.assert_status(signed_event(), 200)
        self.ssm.get_parameter.assert_called_once()
        self.assertEqual(self.sqs.send_message.call_count, 2)
        self.assertEqual(self.clients.call_count, 2)

    def test_ssm_failure_not_cached_and_never_leaks_details(self):
        private_detail = "sensitive-aws-error-detail"
        self.ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": private_detail}}, "GetParameter"
        )
        with self.assertLogs("lambdas.webhook", level="ERROR") as logs:
            result = self.assert_not_queued(signed_event(), 500)
        self.assertNotIn(private_detail, result["body"] + " ".join(logs.output))
        self.assertIn("ssm_get_parameter", " ".join(logs.output))
        self.ssm.get_parameter.side_effect = None
        self.assert_status(signed_event(), 200)
        self.assertEqual(self.ssm.get_parameter.call_count, 2)

    def test_nonsecure_or_empty_secret_is_rejected(self):
        for parameter in (
            {"Type": "String", "Value": SECRET},
            {"Type": "SecureString", "Value": ""},
            {"Type": "SecureString", "Value": 123}, {},
        ):
            with self.subTest(parameter=parameter):
                self.ssm.get_parameter.return_value = {"Parameter": parameter}
                self.assert_not_queued(signed_event(), 500)
        self.assertEqual(self.ssm.get_parameter.call_count, 4)

    def test_sqs_failure_returns_server_error_and_safe_context(self):
        private_detail = "sensitive-queue-error-detail"
        self.sqs.send_message.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": private_detail}}, "SendMessage"
        )
        with self.assertLogs("lambdas.webhook", level="ERROR") as logs:
            result = self.assert_status(signed_event(), 500)
        output = " ".join(logs.output)
        self.assertNotIn(private_detail, result["body"] + output)
        for field in ("job_id", "repository", "flavor"):
            self.assertIn(field, output)
        self.assertIn("sqs_send_message", output)

    def test_logs_exclude_secret_signature_and_full_payload(self):
        event = signed_event()
        with self.assertLogs("lambdas.webhook", level="INFO") as logs:
            self.assert_status(event, 200)
        output = " ".join(logs.output)
        for value in (SECRET, event["headers"]["X-Hub-Signature-256"], "not-forwarded", "unneeded_field"):
            self.assertNotIn(value, output)


if __name__ == "__main__":
    unittest.main()
