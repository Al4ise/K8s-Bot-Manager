import os
import uuid
import logging
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from typing import Dict, Optional

from GitConfig import GitConfig
from BotConfig import BotConfig

import docker
from docker.errors import BuildError, APIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BotManager:
    def __init__(self):
        try:
            config.load_kube_config()
            self.kubernetes_core_api = client.CoreV1Api()
            self.kubernetes_rbac_api = client.RbacAuthorizationV1Api()
            self.kubernetes_apps_api = client.AppsV1Api()
            self.kubernetes_auth_api = client.AuthenticationV1Api()
            self.bots: Dict[str, Dict] = {}
        except Exception as exception:
            logger.error(f"Failed to load Kubernetes configuration: {exception}")
            raise

    def is_authenticated_with_lumiwealth(self) -> bool:
        # Implement Lumiwealth authentication check here
        return True

    def validate_configuration(self, configuration: Dict) -> bool:
        # TODO more rigorous validation, needs to be everything proof
        required_fields = ["resources"]
        for field in required_fields:
            if field not in configuration:
                logger.error(f"Missing required configuration field: {field}")
                return False
        return True

    def create_namespace(self, user_id: str, bot_id: str) -> str:
        namespace_name = f"bot-{user_id}-{bot_id}"
        namespace_body = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace_name,
                labels={"name": namespace_name}
            )
        )
        try:
            self.kubernetes_core_api.create_namespace(namespace_body)
            logger.info(f"Namespace '{namespace_name}' created.")
        except ApiException as api_exception:
            if api_exception.status == 409:
                logger.warning(f"Namespace '{namespace_name}' already exists.")
            else:
                logger.error(f"Failed to create namespace: {api_exception}")
                raise
        return namespace_name

    def setup_rbac(self, namespace: str):
        try:
            # Create a dedicated service account
            service_account = client.V1ServiceAccount(
                metadata=client.V1ObjectMeta(name="bot-service-account")
            )
            self.kubernetes_core_api.create_namespaced_service_account(namespace, service_account)
            logger.info("Service account 'bot-service-account' created.")

            # Create a role with least privileges
            role = client.V1Role(
                metadata=client.V1ObjectMeta(namespace=namespace, name="bot-role"),
                rules=[
                    client.V1PolicyRule(
                        api_groups=[""],
                        resources=[],
                        verbs=[]
                    )
                ]
            )
            self.kubernetes_rbac_api.create_namespaced_role(namespace, role)
            logger.info("RBAC role 'bot-role' created.")

            # Bind the role to the service account
            role_binding = client.V1RoleBinding(
                metadata=client.V1ObjectMeta(namespace=namespace, name="bot-rolebinding"),
                subjects=[client.RbacV1Subject(
                    kind="ServiceAccount",
                    name="bot-service-account",
                    namespace=namespace
                )],
                role_ref=client.V1RoleRef(
                    kind="Role",
                    name="bot-role",
                    api_group="rbac.authorization.k8s.io"
                )
            )
            self.kubernetes_rbac_api.create_namespaced_role_binding(namespace, role_binding)
            logger.info("RBAC role binding 'bot-rolebinding' created.")
        except ApiException as api_exception:
            logger.error(f"Failed to create RBAC resources: {api_exception}")
            raise

    def create_secret(self, namespace: str, broker_config: Dict):
        secret_name = "broker-secrets"
        metadata = client.V1ObjectMeta(name=secret_name)
        # Remove any None values
        data = {k: str(v) for k, v in broker_config.items() if v is not None}
        secret = client.V1Secret(
            metadata=metadata,
            string_data=data,
            type="Opaque",
        )
        try:
            self.kubernetes_core_api.create_namespaced_secret(namespace, secret)
            logger.info(f"Secret '{secret_name}' created in namespace '{namespace}'.")
        except ApiException as api_exception:
            if api_exception.status == 409:
                logger.warning(f"Secret '{secret_name}' already exists in namespace '{namespace}'.")
            else:
                logger.error(f"Failed to create secret: {api_exception}")
                raise

    def deploy_bot_pod(self, bot_config: BotConfig, git_config: GitConfig) -> str:
        namespace_name = self.create_namespace(bot_config.user_id, bot_config.bot_id)
        self.setup_rbac(namespace_name)
        self.create_secret(namespace_name, bot_config.broker_config)

        pod_name = f"bot-{bot_config.bot_id}"
        pod_manifest = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                namespace=namespace_name,
                labels={"app": "bot", "bot_id": bot_config.bot_id}
            ),
            spec=client.V1PodSpec(
                service_account_name="bot-service-account",
                automount_service_account_token=False,
                security_context=client.V1PodSecurityContext(
                    run_as_non_root=True,
                    run_as_user=1000,
                    run_as_group=3000,
                    fs_group=2000
                ),
                containers=[
                    client.V1Container(
                        name="bot",
                        image=bot_config.image,
                        image_pull_policy="Always",
                        resources=client.V1ResourceRequirements(**bot_config.resources),
                        env=[
                            client.V1EnvVar(
                                name=k,
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="broker-secrets",
                                        key=k,
                                    )
                                ),
                            )
                            for k in bot_config.broker_config.keys()
                        ],
                        security_context=client.V1SecurityContext(
                            run_as_non_root=True,
                            allow_privilege_escalation=False,
                            read_only_root_filesystem=True,
                            capabilities=client.V1Capabilities(
                                drop=["ALL"]
                            )
                        ),
                    )
                ],
                restart_policy="Never",
                image_pull_secrets=[client.V1LocalObjectReference(name="registry-credentials")]
            ),
        )
        try:
            self.kubernetes_core_api.create_namespaced_pod(namespace_name, pod_manifest)
            logger.info(f"Pod '{pod_name}' deployed in namespace '{namespace_name}'.")
            return namespace_name
        except ApiException as api_exception:
            logger.error(f"Failed to deploy pod: {api_exception}")
            raise

    def terminate_bot_pod(self, namespace: str, pod_name: str):
        try:
            self.kubernetes_core_api.delete_namespaced_pod(pod_name, namespace)
            logger.info(f"Pod '{pod_name}' deleted from namespace '{namespace}'.")
        except ApiException as api_exception:
            if api_exception.status == 404:
                logger.warning(f"Pod '{pod_name}' not found in namespace '{namespace}'.")
            else:
                logger.error(f"Failed to delete pod: {api_exception}")
                raise

    def retrieve_pod_logs(self, namespace: str, pod_name: str) -> str:
        try:
            logs = self.kubernetes_core_api.read_namespaced_pod_log(pod_name, namespace)
            return logs
        except ApiException as api_exception:
            logger.error(f"Failed to get logs for pod '{pod_name}': {api_exception}")
            raise

    def build_and_deploy_bot(self, bot_config: BotConfig, git_config: GitConfig) -> str:
        try:
            repository_path = git_config.clone_repository(bot_config.repository_url)
            if not repository_path:
                raise ValueError("Failed to clone repository")

            docker_client = docker.from_env()
            docker_image_tag = f"bot:{uuid.uuid4().hex[:8]}"

            image, build_logs = docker_client.images.build(
                path=repository_path,
                tag=docker_image_tag,
                buildargs=bot_config.build_parameters,
                rm=True
            )
            logger.info(f"Docker image '{docker_image_tag}' built successfully.")

            bot_config.image = docker_image_tag
            return self.deploy_bot_pod(bot_config, git_config)
        except BuildError as build_error:
            logger.error(f"Docker build failed: {build_error}")
            raise
        except APIError as api_error:
            logger.error(f"Docker API error: {api_error}")
            raise
        except Exception as exception:
            logger.error(f"Failed to build and deploy bot: {exception}")
            raise

    def add_bot(self, bot_config: BotConfig, git_config: GitConfig) -> str:
        namespace = self.build_and_deploy_bot(bot_config, git_config)
        self.bots[bot_config.bot_id] = {
            'config': bot_config,
            'namespace': namespace,
            'logs': ''
        }
        logger.info(f"Bot '{bot_config.bot_id}' added and deployed in namespace '{namespace}'.")
        return bot_config.bot_id

    def remove_bot(self, bot_id: str):
        bot = self.bots.get(bot_id)
        if bot:
            pod_name = f"bot-{bot_id}"
            self.terminate_bot_pod(bot['namespace'], pod_name)
            del self.bots[bot_id]
            logger.info(f"Bot '{bot_id}' has been removed and terminated.")
        else:
            logger.error(f"Bot with ID '{bot_id}' not found.")

    def get_bot_logs(self, bot_id: str) -> Optional[str]:
        bot = self.bots.get(bot_id)
        if bot:
            pod_name = f"bot-{bot_id}"
            logs = self.retrieve_pod_logs(bot['namespace'], pod_name)
            bot['logs'] = logs
            return logs
        else:
            logger.error(f"Bot with ID '{bot_id}' not found.")
            return None

    def list_bots(self) -> Dict[str, Dict]:
        return self.bots

    def update_bot_config(self, bot_id: str, new_config: BotConfig, git_config: GitConfig):
        bot = self.bots.get(bot_id)
        if bot:
            # Terminate existing bot
            pod_name = f"bot-{bot_id}"
            self.terminate_bot_pod(bot['namespace'], pod_name)
            logger.info(f"Bot '{bot_id}' pod terminated for configuration update.")

            # Update configuration
            bot['config'] = new_config
            logger.info(f"Configuration for bot '{bot_id}' has been updated.")

            # Redeploy bot with new configuration
            namespace = self.build_and_deploy_bot(new_config, git_config)
            bot['namespace'] = namespace
            logger.info(f"Bot '{bot_id}' redeployed in namespace '{namespace}'.")
        else:
            logger.error(f"Bot with ID '{bot_id}' not found.")
