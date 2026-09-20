import json
import traceback
import unittest
from dataclasses import asdict, replace
from unittest.mock import MagicMock, Mock, patch

import boto3
import jwt
import requests
from botocore.exceptions import ClientError
from botocore.validate import validate_parameters
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from lambdas.provisioner import ec2, github, jit_store, main
from lambdas.provisioner.config import ConfigurationError, load_config
from lambdas.provisioner.models import MessageError, parse_request


ENV = {
    "GITHUB_APP_ID": "123456",
    "GITHUB_PRIVATE_KEY_PARAMETER": "/tests/app-key",
    "GITHUB_RUNNER_GROUP_ID": "1",
    "RUNNER_LAUNCH_TEMPLATE_ID": "lt-0123456789abcdef0",
    "RUNNER_SUBNET_IDS": "subnet-aaa,subnet-bbb",
    "GENERAL_INSTANCE_TYPE": "t3.medium",
    "HEAVY_INSTANCE_TYPE": "c7i.2xlarge",
    "MAX_RUNNERS": "2",
    "JIT_PARAMETER_PREFIX": "/tests/jit",
}
MESSAGE = {
    "job_id": 123,
    "run_id": 456,
    "repository": "example/project",
    "flavor": "heavy",
    "labels": ["self-hosted", "heavy"],
    "installation_id": 789,
}
REQUEST = parse_request(json.dumps(MESSAGE))
CONFIG = load_config(ENV)
JIT_NAME = "/tests/jit/123"


def sqs_event(*messages):
    return {"Records": [{"messageId": str(index), "body": json.dumps(message)}
                        for index, message in enumerate(messages or (MESSAGE,))]}


def aws_error(code, operation="GetParameter", message="private-error-detail"):
    return ClientError({"Error": {"Code": code, "Message": message}}, operation)


class ConfigTests(unittest.TestCase):
    def test_valid_configuration_and_default_version(self):
        self.assertEqual(CONFIG.github_app_id, "123456")
        self.assertEqual(CONFIG.github_runner_group_id, 1)
        self.assertEqual(CONFIG.launch_template_version, "$Latest")
        self.assertEqual(CONFIG.max_runners, 2)
        self.assertEqual(CONFIG.instance_type("general"), "t3.medium")
        self.assertEqual(CONFIG.instance_type("heavy"), "c7i.2xlarge")

    def test_explicit_template_version(self):
        for version in ("7", "$Default"):
            with self.subTest(version=version):
                config = load_config({**ENV, "RUNNER_LAUNCH_TEMPLATE_VERSION": version})
                self.assertEqual(config.launch_template_version, version)

    def test_two_subnet_ids(self):
        self.assertEqual(CONFIG.runner_subnet_ids, ("subnet-aaa", "subnet-bbb"))

    def test_subnet_whitespace_is_stripped(self):
        config = load_config({**ENV, "RUNNER_SUBNET_IDS": "  subnet-aaa , \t subnet-bbb  "})
        self.assertEqual(config.runner_subnet_ids, ("subnet-aaa", "subnet-bbb"))

    def test_empty_subnet_entries_are_rejected(self):
        for value in (",", " , ", "subnet-aaa,", ",subnet-bbb", "subnet-aaa,,subnet-bbb",
                      "subnet-aaa,   ,subnet-bbb"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ConfigurationError, "RUNNER_SUBNET_IDS"):
                    load_config({**ENV, "RUNNER_SUBNET_IDS": value})

    def test_missing_or_empty_required_configuration(self):
        for key in ENV:
            for value in (None, "", " "):
                with self.subTest(key=key, value=value):
                    env = dict(ENV)
                    if value is None:
                        del env[key]
                    else:
                        env[key] = value
                    with self.assertRaisesRegex(ConfigurationError, key):
                        load_config(env)

    def test_invalid_configuration(self):
        cases = {
            "GITHUB_APP_ID": ["abc", "-1", "0"],
            "GITHUB_RUNNER_GROUP_ID": ["0", "1.5"],
            "MAX_RUNNERS": ["-1", "0", "1.5", "true"],
            "RUNNER_LAUNCH_TEMPLATE_ID": ["ami-1234", "name"],
            "RUNNER_LAUNCH_TEMPLATE_VERSION": ["", "0", "bad"],
            "GENERAL_INSTANCE_TYPE": ["bad", "t3.medium extra"],
            "HEAVY_INSTANCE_TYPE": ["bad"],
            "GITHUB_PRIVATE_KEY_PARAMETER": ["/contains spaces"],
            "JIT_PARAMETER_PREFIX": ["relative", "/", "/a//b", "/aws/test", "/ssm/test", "/" + "a" * 181],
        }
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(ConfigurationError, key):
                        load_config({**ENV, key: value})

    def test_prefix_trailing_slash_is_normalized(self):
        self.assertEqual(load_config({**ENV, "JIT_PARAMETER_PREFIX": "/test/jit/"}).jit_parameter_prefix,
                         "/test/jit")

    def test_unknown_flavor_has_no_instance_type(self):
        with self.assertRaises(ConfigurationError):
            CONFIG.instance_type("gpu")


class MessageTests(unittest.TestCase):
    def test_valid_internal_contract(self):
        self.assertEqual(json.loads(json.dumps(asdict(REQUEST))), MESSAGE)

    def test_invalid_json(self):
        for body in ("{", "null", "[]", "1", '{"id":NaN}', None, {}):
            with self.subTest(body=body):
                with self.assertRaises(MessageError):
                    parse_request(body)

    def test_missing_fields(self):
        for field in MESSAGE:
            with self.subTest(field=field):
                message = dict(MESSAGE)
                del message[field]
                with self.assertRaises(MessageError):
                    parse_request(json.dumps(message))

    def test_invalid_field_types(self):
        cases = {
            "job_id": [True, 0, -1, "123", 1.5, 2**63],
            "run_id": [False, 0, "456"],
            "installation_id": [0, "789"],
            "repository": [None, "invalid", "owner/../repo", "owner/..", "owner/repo?x=1"],
            "flavor": [None, "gpu", [], {}],
            "labels": [None, "heavy", [], [""], ["heavy", 1], ["label"] * 101],
        }
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(MessageError):
                        parse_request(json.dumps({**MESSAGE, field: value}))

    def test_no_webhook_policy_is_repeated(self):
        message = {**MESSAGE, "repository": "another/repository", "flavor": "general",
                   "labels": ["linux", "custom-label"]}
        self.assertEqual(parse_request(json.dumps(message)).flavor, "general")


class GitHubTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("lambdas.provisioner.github.requests.post")
        self.post = patcher.start()
        self.addCleanup(patcher.stop)
        self.response = MagicMock()
        self.response.status_code = 201
        self.post.return_value.__enter__.return_value = self.response

    def test_real_rs256_signature_and_reference_claims(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
        with patch("lambdas.provisioner.github.time.time", return_value=2000000000):
            token = github.generate_app_jwt("123456", pem)
        claims = jwt.decode(token, key.public_key(), algorithms=["RS256"],
                            options={"verify_exp": False, "verify_iat": False})
        self.assertEqual(claims, {"iat": 1999999940, "exp": 2000000600, "iss": "123456"})
        self.assertEqual(jwt.get_unverified_header(token)["alg"], "RS256")

    def test_signing_failure_is_safe(self):
        with patch("lambdas.provisioner.github.jwt.encode", side_effect=ValueError("private-key-value")):
            with self.assertRaises(github.GitHubError) as raised:
                github.generate_app_jwt("123456", "private-key-value")
        self.assertNotIn("private-key-value", "".join(traceback.format_exception(raised.exception)))

    def test_installation_token_matches_reference_flow(self):
        self.response.json.return_value = {"token": "installation-secret"}
        self.assertEqual(github.installation_token("jwt-secret", 789), "installation-secret")
        self.post.assert_called_once_with(
            "https://api.github.com/app/installations/789/access_tokens",
            headers={"Authorization": "Bearer jwt-secret", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
            json=None, timeout=(5, 30), allow_redirects=False,
        )

    def test_repository_jit_request(self):
        self.response.json.return_value = {"encoded_jit_config": "jit-secret"}
        self.assertEqual(github.generate_jit_config(REQUEST, "installation-secret", 7), "jit-secret")
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], "https://api.github.com/repos/example/project/actions/runners/generate-jitconfig")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer installation-secret")
        payload = kwargs["json"]
        self.assertEqual(payload["labels"], MESSAGE["labels"])
        self.assertEqual(payload["work_folder"], "_work")
        self.assertEqual(payload["runner_group_id"], 7)
        self.assertRegex(payload["name"], r"^github-job-123-[0-9a-f]{32}$")
        github.generate_jit_config(REQUEST, "installation-secret", 7)
        self.assertNotEqual(self.post.call_args.kwargs["json"]["name"], payload["name"])

    def test_http_error_does_not_expose_body_or_credentials(self):
        for status in (302, 401, 403, 422, 500):
            with self.subTest(status=status):
                self.response.status_code = status
                self.response.text = "private-response"
                with self.assertRaisesRegex(github.GitHubError, str(status)) as raised:
                    github.installation_token("jwt-secret", 789)
                self.assertNotIn("private-response", str(raised.exception))
                self.assertNotIn("jwt-secret", str(raised.exception))
        self.response.json.assert_not_called()

    def test_network_and_invalid_json_fail_safely(self):
        self.post.side_effect = requests.Timeout("jwt-secret")
        with self.assertRaises(github.GitHubError) as raised:
            github.installation_token("jwt-secret", 789)
        self.assertNotIn("jwt-secret", "".join(traceback.format_exception(raised.exception)))
        self.post.side_effect = None
        self.response.json.side_effect = ValueError("private-response")
        with self.assertRaises(github.GitHubError):
            github.installation_token("jwt-secret", 789)

    def test_missing_credentials_in_response(self):
        for value in ({}, {"token": ""}, {"token": 123}, [], None):
            with self.subTest(value=value):
                self.response.json.return_value = value
                with self.assertRaises(github.GitHubError):
                    github.installation_token("jwt-secret", 789)
        for value in ({}, {"encoded_jit_config": ""}, {"encoded_jit_config": 123}):
            with self.subTest(value=value):
                self.response.json.return_value = value
                with self.assertRaises(github.GitHubError):
                    github.generate_jit_config(REQUEST, "installation-secret", 1)


class StoreTests(unittest.TestCase):
    def test_read_decrypts_and_checks_secure_string(self):
        ssm = Mock()
        ssm.get_parameter.return_value = {"Parameter": {"Type": "SecureString", "Value": "secret"}}
        self.assertEqual(jit_store.read_secure_parameter(ssm, "/test/key"), "secret")
        ssm.get_parameter.assert_called_once_with(Name="/test/key", WithDecryption=True)
        for parameter in ({"Type": "String", "Value": "secret"}, {"Type": "SecureString", "Value": ""}):
            ssm.get_parameter.return_value = {"Parameter": parameter}
            with self.assertRaises(ValueError):
                jit_store.read_secure_parameter(ssm, "/test/key")

    def test_only_missing_parameter_allows_generation(self):
        ssm = Mock()
        ssm.get_parameter.side_effect = aws_error("ParameterNotFound")
        self.assertIsNone(jit_store.read_jit_config(ssm, JIT_NAME))
        ssm.get_parameter.side_effect = aws_error("AccessDeniedException")
        with self.assertRaises(ClientError):
            jit_store.read_jit_config(ssm, JIT_NAME)

    def test_store_secure_string_without_overwrite(self):
        ssm = Mock()
        jit_store.store_jit_config(ssm, JIT_NAME, "jit-secret")
        ssm.put_parameter.assert_called_once_with(Name=JIT_NAME, Value="jit-secret", Type="SecureString",
                                                   Overwrite=False, Tier="Intelligent-Tiering")


class EC2Tests(unittest.TestCase):
    def test_capacity_filters_and_pagination(self):
        client = Mock()
        client.get_paginator.return_value.paginate.return_value = [
            {"Reservations": [{"Instances": [{"InstanceId": "i-first"}]}]},
            {"Reservations": [{"Instances": [{"InstanceId": "i-second"}]}]},
        ]
        ec2.check_capacity(client, 3)
        client.get_paginator.assert_called_with("describe_instances")
        client.get_paginator.return_value.paginate.assert_called_with(Filters=[
            {"Name": "tag:ManagedBy", "Values": ["gha-runners"]},
            {"Name": "instance-state-name", "Values": ["pending", "running"]},
        ])
        for maximum in (2, 1):
            with self.subTest(maximum=maximum):
                with self.assertRaises(ec2.CapacityError):
                    ec2.check_capacity(client, maximum)

    def test_create_fleet_parameters_and_sdk_shape(self):
        client = Mock()
        client.create_fleet.return_value = {"Instances": [{"InstanceIds": ["i-runner"]}]}
        shape = boto3.Session()._session.get_service_model("ec2").operation_model("CreateFleet").input_shape
        for flavor, instance_type in (("general", "t3.medium"), ("heavy", "c7i.2xlarge")):
            with self.subTest(flavor=flavor):
                client.reset_mock()
                request = replace(REQUEST, flavor=flavor)
                self.assertEqual(ec2.create_runner(client, CONFIG, request, JIT_NAME), "i-runner")
                client.create_fleet.assert_called_once()
                kwargs = client.create_fleet.call_args.kwargs
                validate_parameters(kwargs, shape)
                self.assertEqual(kwargs["Type"], "instant")
                self.assertEqual(kwargs["ClientToken"], "github-job-123")
                self.assertEqual(kwargs["LaunchTemplateConfigs"], [{
                    "LaunchTemplateSpecification": {"LaunchTemplateId": ENV["RUNNER_LAUNCH_TEMPLATE_ID"],
                                                    "Version": "$Latest"},
                    "Overrides": [
                        {"SubnetId": "subnet-aaa", "InstanceType": instance_type},
                        {"SubnetId": "subnet-bbb", "InstanceType": instance_type},
                    ],
                }])
                self.assertEqual(kwargs["TargetCapacitySpecification"], {
                    "TotalTargetCapacity": 1, "OnDemandTargetCapacity": 1,
                    "SpotTargetCapacity": 0, "DefaultTargetCapacityType": "on-demand",
                })
                specification = kwargs["TagSpecifications"][0]
                self.assertEqual(specification["ResourceType"], "instance")
                self.assertEqual({tag["Key"]: tag["Value"] for tag in specification["Tags"]}, {
                    "ManagedBy": "gha-runners", "Repository": "example/project", "Flavor": flavor,
                    "JobId": "123", "RunId": "456", "JIT_PARAMETER_NAME": JIT_NAME,
                })
                self.assertNotIn("UserData", json.dumps(kwargs))

    def test_single_subnet_still_requests_one_runner(self):
        client = Mock()
        client.create_fleet.return_value = {"Instances": [{"InstanceIds": ["i-runner"]}]}
        config = load_config({**ENV, "RUNNER_SUBNET_IDS": "subnet-aaa"})
        ec2.create_runner(client, config, REQUEST, JIT_NAME)
        client.create_fleet.assert_called_once()
        kwargs = client.create_fleet.call_args.kwargs
        self.assertEqual(kwargs["LaunchTemplateConfigs"][0]["Overrides"], [
            {"SubnetId": "subnet-aaa", "InstanceType": "c7i.2xlarge"},
        ])
        self.assertEqual(kwargs["TargetCapacitySpecification"]["TotalTargetCapacity"], 1)

    def test_configured_template_version_and_deterministic_token(self):
        client = Mock()
        client.create_fleet.return_value = {"Instances": [{"InstanceIds": ["i-runner"]}]}
        config = replace(CONFIG, launch_template_version="7")
        ec2.create_runner(client, config, REQUEST, JIT_NAME)
        ec2.create_runner(client, config, REQUEST, JIT_NAME)
        self.assertEqual(client.create_fleet.call_args_list[0], client.create_fleet.call_args_list[1])
        specification = client.create_fleet.call_args.kwargs["LaunchTemplateConfigs"][0]["LaunchTemplateSpecification"]
        self.assertEqual(specification["Version"], "7")
        self.assertNotEqual(ec2.client_token(123), ec2.client_token(124))

    def test_fleet_acceptance_without_an_instance_is_failure(self):
        client = Mock()
        for result in ({"FleetId": "fleet-id"}, {"Errors": [{"ErrorMessage": "private-detail"}]},
                       {"Instances": []}, {"Instances": [{"InstanceIds": ["i-1", "i-2"]}]}):
            with self.subTest(result=result):
                client.create_fleet.return_value = result
                with self.assertRaises(ec2.FleetError) as raised:
                    ec2.create_runner(client, CONFIG, REQUEST, JIT_NAME)
                self.assertNotIn("private-detail", str(raised.exception))


class HandlerTests(unittest.TestCase):
    def setUp(self):
        main.aws_client.cache_clear()
        self.addCleanup(main.aws_client.cache_clear)
        env = patch.dict("os.environ", ENV, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.ec2 = Mock()
        self.ssm = Mock()
        clients = patch("boto3.client", side_effect={"ec2": self.ec2, "ssm": self.ssm}.__getitem__)
        self.clients = clients.start()
        self.addCleanup(clients.stop)
        self.parameters = {ENV["GITHUB_PRIVATE_KEY_PARAMETER"]: "private-key-secret"}
        self.instances = []
        self.capacity = 0
        self.ec2.get_paginator.return_value.paginate.side_effect = self.describe_instances
        self.ec2.create_fleet.side_effect = self.create_fleet
        self.ssm.get_parameter.side_effect = self.get_parameter
        self.ssm.put_parameter.side_effect = self.put_parameter
        self.ssm.delete_parameter.side_effect = lambda **kwargs: self.parameters.pop(kwargs["Name"])
        for name, value in (("generate_app_jwt", "jwt-secret"), ("installation_token", "installation-secret"),
                            ("generate_jit_config", "jit-secret")):
            patcher = patch(f"lambdas.provisioner.main.{name}", return_value=value)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def describe_instances(self, **kwargs):
        filters = {item["Name"]: item["Values"] for item in kwargs["Filters"]}
        if "tag:JobId" in filters:
            instances = [instance for instance in self.instances
                         if any(tag["Key"] == "JobId" and tag["Value"] in filters["tag:JobId"]
                                for tag in instance["Tags"])]
        else:
            instances = [{}] * self.capacity
        return [{"Reservations": [{"Instances": instances}]}]

    def create_fleet(self, **kwargs):
        instance_id = f"i-runner-{len(self.instances)}"
        self.instances.append({"InstanceId": instance_id, "ClientToken": kwargs["ClientToken"],
                               "Tags": kwargs["TagSpecifications"][0]["Tags"]})
        return {"FleetId": "fleet-test", "Instances": [{"InstanceIds": [instance_id]}]}

    def get_parameter(self, **kwargs):
        if kwargs["Name"] not in self.parameters:
            raise aws_error("ParameterNotFound")
        return {"Parameter": {"Type": "SecureString", "Value": self.parameters[kwargs["Name"]]}}

    def put_parameter(self, **kwargs):
        if kwargs["Name"] in self.parameters:
            raise aws_error("ParameterAlreadyExists", "PutParameter")
        self.parameters[kwargs["Name"]] = kwargs["Value"]
        return {"Version": 1}

    def test_complete_provisioning_flow(self):
        self.assertIsNone(main.lambda_handler(sqs_event(), None))
        self.generate_app_jwt.assert_called_once_with("123456", "private-key-secret")
        self.installation_token.assert_called_once_with("jwt-secret", 789)
        self.generate_jit_config.assert_called_once_with(REQUEST, "installation-secret", 1)
        self.assertEqual(self.parameters[JIT_NAME], "jit-secret")
        self.ec2.create_fleet.assert_called_once()
        self.ssm.delete_parameter.assert_not_called()
        self.assertNotIn("jit-secret", json.dumps(self.ec2.create_fleet.call_args.kwargs))

    def test_multiple_records(self):
        main.lambda_handler(sqs_event(MESSAGE, {**MESSAGE, "job_id": 124}), None)
        self.assertEqual(self.ec2.create_fleet.call_count, 2)
        self.assertEqual(self.generate_jit_config.call_count, 2)
        self.assertIn("/tests/jit/124", self.parameters)

    def test_invalid_batch_is_rejected_before_any_aws_call(self):
        for event in (None, {}, {"Records": {}}, {"Records": [None]}, {"Records": [{}]},
                      {"Records": [{"body": "{"}]}, sqs_event(MESSAGE, {**MESSAGE, "flavor": "unknown"})):
            with self.subTest(event=event):
                with self.assertRaises(MessageError):
                    main.lambda_handler(event, None)
        self.clients.assert_not_called()
        self.ec2.create_fleet.assert_not_called()

    def test_invalid_config_is_rejected_before_aws_calls(self):
        with patch.dict("os.environ", {"MAX_RUNNERS": "0"}):
            with self.assertRaises(ConfigurationError):
                main.lambda_handler(sqs_event(), None)
        self.clients.assert_not_called()

    def test_invalid_subnets_are_rejected_before_aws_calls(self):
        with patch.dict("os.environ", {"RUNNER_SUBNET_IDS": "subnet-aaa,"}):
            with self.assertRaisesRegex(ConfigurationError, "RUNNER_SUBNET_IDS"):
                main.lambda_handler(sqs_event(), None)
        self.clients.assert_not_called()

    def test_capacity_failure_precedes_github_and_ssm(self):
        for count in (2, 3):
            with self.subTest(count=count):
                self.capacity = count
                with self.assertRaises(ec2.CapacityError):
                    main.lambda_handler(sqs_event(), None)
        self.generate_app_jwt.assert_not_called()
        self.ssm.get_parameter.assert_not_called()
        self.ec2.create_fleet.assert_not_called()

    def test_redelivery_after_bootstrap_consumed_parameter_does_not_relaunch(self):
        main.lambda_handler(sqs_event(), None)
        del self.parameters[JIT_NAME]
        self.capacity = 2
        main.lambda_handler(sqs_event(), None)
        self.ec2.create_fleet.assert_called_once()
        self.generate_jit_config.assert_called_once()
        self.assertNotIn(JIT_NAME, self.parameters)
        filters = self.ec2.get_paginator.return_value.paginate.call_args.kwargs["Filters"]
        self.assertEqual(filters, [
            {"Name": "tag:ManagedBy", "Values": ["gha-runners"]},
            {"Name": "tag:JobId", "Values": ["123"]},
        ])

    def test_existing_runner_must_match_request(self):
        main.lambda_handler(sqs_event(), None)
        with self.assertRaises(ec2.FleetError):
            main.lambda_handler(sqs_event({**MESSAGE, "repository": "another/project"}), None)
        self.ec2.create_fleet.assert_called_once()

    def test_stored_jit_is_reused_after_interrupted_invocation(self):
        self.parameters[JIT_NAME] = "existing-jit-secret"
        main.lambda_handler(sqs_event(), None)
        self.generate_app_jwt.assert_not_called()
        self.ssm.put_parameter.assert_not_called()
        self.ec2.create_fleet.assert_called_once()
        self.assertEqual(self.parameters[JIT_NAME], "existing-jit-secret")

    def test_github_failure_never_creates_fleet(self):
        self.generate_jit_config.side_effect = github.GitHubError("GitHub API request failed with HTTP 403")
        with self.assertRaises(github.GitHubError):
            main.lambda_handler(sqs_event(), None)
        self.ssm.put_parameter.assert_not_called()
        self.ec2.create_fleet.assert_not_called()

    def test_ssm_write_failure_never_creates_fleet_or_deletes_existing_parameter(self):
        self.ssm.put_parameter.side_effect = aws_error("ParameterAlreadyExists", "PutParameter")
        with self.assertRaises(main.ProvisioningError):
            main.lambda_handler(sqs_event(), None)
        self.ec2.create_fleet.assert_not_called()
        self.ssm.delete_parameter.assert_not_called()

    def test_fleet_failure_cleans_up_new_parameter(self):
        original = aws_error("InsufficientInstanceCapacity", "CreateFleet")
        self.ec2.create_fleet.side_effect = original
        with self.assertRaises(ClientError) as raised:
            main.provision_runner(REQUEST, CONFIG, self.ec2, self.ssm)
        self.assertIs(raised.exception, original)
        self.ssm.delete_parameter.assert_called_once_with(Name=JIT_NAME)
        self.assertNotIn(JIT_NAME, self.parameters)

    def test_unfulfilled_fleet_response_also_cleans_up(self):
        self.ec2.create_fleet.side_effect = None
        self.ec2.create_fleet.return_value = {"Errors": [{"ErrorCode": "InsufficientInstanceCapacity"}]}
        with self.assertRaises(ec2.FleetError):
            main.lambda_handler(sqs_event(), None)
        self.ssm.delete_parameter.assert_called_once_with(Name=JIT_NAME)

    def test_cleanup_failure_preserves_original_failure(self):
        original = ec2.FleetError("CreateFleet did not return exactly one runner instance")
        self.ec2.create_fleet.side_effect = original
        self.ssm.delete_parameter.side_effect = RuntimeError("cleanup-private-detail")
        with self.assertLogs("lambdas.provisioner", level="ERROR") as logs:
            with self.assertRaises(ec2.FleetError) as raised:
                main.lambda_handler(sqs_event(), None)
        self.assertIs(raised.exception, original)
        self.assertNotIn("cleanup-private-detail", " ".join(logs.output))
        self.assertIn("JIT cleanup failed", " ".join(logs.output))

    def test_reused_parameter_is_not_deleted_on_failure(self):
        self.parameters[JIT_NAME] = "existing-jit-secret"
        self.ec2.create_fleet.side_effect = ec2.FleetError("Fleet failed")
        with self.assertRaises(ec2.FleetError):
            main.lambda_handler(sqs_event(), None)
        self.ssm.delete_parameter.assert_not_called()

    def test_success_logs_have_context_without_credentials(self):
        with self.assertLogs("lambdas.provisioner", level="INFO") as logs:
            main.lambda_handler(sqs_event(), None)
        output = " ".join(logs.output)
        for secret in ("private-key-secret", "jwt-secret", "installation-secret", "jit-secret"):
            self.assertNotIn(secret, output)
        for field in ("job_id", "repository", "flavor", "instance_id"):
            self.assertIn(field, output)

    def test_unexpected_error_logs_details_and_preserves_cause(self):
        errors = (
            aws_error("AccessDeniedException", message=(
                "Not authorized to perform ssm:GetParameter on resource "
                "arn:aws:ssm:us-east-1:123456789012:parameter/tests/jit/123"
            )),
            RuntimeError("Unexpected API failure"),
        )
        for original in errors:
            with self.subTest(error_type=type(original).__name__):
                self.ssm.get_parameter.side_effect = original
                with self.assertLogs("lambdas.provisioner", level="ERROR") as logs:
                    with self.assertRaises(main.ProvisioningError) as raised:
                        main.lambda_handler(sqs_event(), None)
                record = logs.records[0]
                expected_context = {"job_id": 123, "repository": "example/project", "flavor": "heavy"}
                self.assertEqual(record.getMessage(), (
                    f"Provisioning failed error_type={type(original).__name__} "
                    f"error={original} context={json.dumps(expected_context)}"
                ))
                self.assertIs(record.exc_info[1], original)
                self.assertIsNotNone(record.exc_info[2])
                self.assertIn("Traceback (most recent call last)", " ".join(logs.output))
                self.assertEqual(str(raised.exception), "Runner provisioning failed")
                self.assertIs(raised.exception.__cause__, original)
                self.ec2.create_fleet.assert_not_called()


if __name__ == "__main__":
    unittest.main()
