# Copyright 2017 Cloudbase Solutions Srl
# All Rights Reserved.

import uuid
from unittest import mock

import ddt

from coriolis import constants, exception
from coriolis.conductor.rpc import server
from coriolis.db import api as db_api
from coriolis.db.sqlalchemy import models
from coriolis.tests import test_base, testutils
from coriolis.worker.rpc import client as rpc_worker_client


@ddt.ddt
class ConductorServerEndpointTestCase(test_base.CoriolisBaseTestCase):
    """Test suite for the Coriolis Conductor RPC server."""

    def setUp(self):
        super(ConductorServerEndpointTestCase, self).setUp()
        self.server = server.ConductorServerEndpoint()

    @mock.patch.object(
        rpc_worker_client.WorkerClient, "from_service_definition"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "_scheduler_client")
    def test_get_all_diagnostics(self, mock_scheduler_client, _):
        mock_scheduler_client.get_workers_for_specs.side_effect = Exception()
        self.assertRaises(
            Exception,
            lambda: self.server.get_all_diagnostics(mock.sentinel.context),
        )
        mock_scheduler_client.get_workers_for_specs.side_effect = None

        diagnostics = self.server.get_all_diagnostics(mock.sentinel.context)
        assert (
            mock_scheduler_client.get_diagnostics.return_value in diagnostics
        )

    @mock.patch.object(
        rpc_worker_client.WorkerClient, "from_service_definition"
    )
    @mock.patch.object(db_api, "get_service")
    @mock.patch.object(server.ConductorServerEndpoint, "_scheduler_client")
    def test_get_worker_service_rpc_for_specs(
            self,
            mock_scheduler_client,
            mock_get_service,
            mock_from_service_definition,
    ):
        # returns dictionary with id and rpc
        mock_scheduler_client.get_worker_service_for_specs.return_value = {
            "id": mock.sentinel.worker_id
        }
        result = self.server._get_worker_service_rpc_for_specs(
            mock.sentinel.context
        )

        worker_service = mock_scheduler_client.get_worker_service_for_specs
        worker_service.assert_called_once_with(
            mock.sentinel.context,
            provider_requirements=None,
            region_sets=None,
            enabled=True,
            random_choice=False,
            raise_on_no_matches=True,
        )
        mock_get_service.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.worker_id
        )

        self.assertEqual(result, mock_from_service_definition.return_value)

    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    @mock.patch.object(db_api, "delete_endpoint")
    @mock.patch.object(db_api, "update_endpoint")
    @mock.patch.object(db_api, "add_endpoint")
    @mock.patch.object(models, "Endpoint")
    @mock.patch.object(uuid, "uuid4")
    def test_create_endpoint(
            self,
            mock_uuid4,
            mock_endpoint_model,
            mock_add_endpoint,
            mock_update_endpoint,
            mock_delete_endpoint,
            mock_get_endpoint,
    ):
        endpoint = self.server.create_endpoint(
            mock.sentinel.context,
            mock.sentinel.name,
            mock.sentinel.endpoint_type,
            mock.sentinel.description,
            mock.sentinel.connection_info,
        )
        self.assertEqual(
            mock_endpoint_model.return_value.name, mock.sentinel.name
        )
        self.assertEqual(
            mock_endpoint_model.return_value.type, mock.sentinel.endpoint_type
        )
        self.assertEqual(
            mock_endpoint_model.return_value.description,
            mock.sentinel.description,
        )
        self.assertEqual(
            mock_endpoint_model.return_value.connection_info,
            mock.sentinel.connection_info,
        )

        mock_add_endpoint.assert_called_once_with(
            mock.sentinel.context, mock_endpoint_model.return_value
        )
        mock_update_endpoint.assert_not_called()
        mock_delete_endpoint.assert_not_called()
        self.assertEqual(endpoint, mock_get_endpoint.return_value)

        # mapped_regions exist
        self.server.create_endpoint(
            mock.sentinel.context,
            mock.sentinel.name,
            mock.sentinel.endpoint_type,
            mock.sentinel.description,
            mock.sentinel.connection_info,
            mock.sentinel.mapped_regions,
        )

        mock_update_endpoint.assert_called_once_with(
            mock.sentinel.context,
            str(mock_uuid4.return_value),
            {"mapped_regions": mock.sentinel.mapped_regions},
        )
        mock_delete_endpoint.assert_not_called()

        # mapped_regions exist and there's an error updating the endpoint
        mock_update_endpoint.side_effect = Exception()
        self.assertRaises(
            Exception,
            lambda: self.server.create_endpoint(
                mock.sentinel.context,
                mock.sentinel.name,
                mock.sentinel.endpoint_type,
                mock.sentinel.description,
                mock.sentinel.connection_info,
                mock.sentinel.mapped_regions,
            ),
        )
        mock_delete_endpoint.assert_called_once_with(
            mock.sentinel.context, str(mock_uuid4.return_value)
        )

    @mock.patch.object(db_api, "get_endpoint")
    @mock.patch.object(db_api, "update_endpoint")
    def test_update_endpoint(self, mock_update_endpoint, mock_get_endpoint):
        endpoint = testutils.get_wrapped_function(self.server.update_endpoint)(
            self,
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.updated_values,  # type: ignore
        )

        mock_update_endpoint.assert_called_once_with(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.updated_values,
        )
        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )
        self.assertEqual(endpoint, mock_get_endpoint.return_value)

    @mock.patch.object(db_api, "get_endpoints")
    def test_get_endpoints(self, mock_get_endpoints):
        endpoints = self.server.get_endpoints(mock.sentinel.context)
        mock_get_endpoints.assert_called_once_with(mock.sentinel.context)
        self.assertEqual(endpoints, mock_get_endpoints.return_value)

    @mock.patch.object(db_api, "get_endpoint")
    def test_get_endpoint(self, mock_get_endpoint):
        def call_get_endpoint():
            return testutils.get_wrapped_function(self.server.get_endpoint)(
                self, mock.sentinel.context,
                mock.sentinel.endpoint_id  # type: ignore
            )

        endpoint = call_get_endpoint()
        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )
        self.assertEqual(endpoint, mock_get_endpoint.return_value)

        # endpoint not found
        mock_get_endpoint.side_effect = exception.NotFound()
        self.assertRaises(exception.NotFound, call_get_endpoint)

    @mock.patch.object(db_api, "delete_endpoint")
    @mock.patch.object(db_api, "get_endpoint_replicas_count")
    def test_delete_endpoint(
            self, mock_get_endpoint_replicas_count, mock_delete_endpoint
    ):
        def call_delete_endpoint():
            return testutils.get_wrapped_function(self.server.delete_endpoint)(
                self, mock.sentinel.context,
                mock.sentinel.endpoint_id  # type: ignore
            )

        mock_get_endpoint_replicas_count.return_value = 0
        call_delete_endpoint()
        mock_delete_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        # endpoint has replicas
        mock_get_endpoint_replicas_count.return_value = 1
        self.assertRaises(exception.NotAuthorized, call_delete_endpoint)

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_get_endpoint_instances(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        instances = self.server.get_endpoint_instances(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.source_environment,
            mock.sentinel.marker,
            mock.sentinel.limit,
            mock.sentinel.instance_name_pattern,
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_ENDPOINT_INSTANCES
                ]
            },
        )
        rpc_return_value = mock_get_worker_service_rpc_for_specs.return_value
        self.assertEqual(
            instances, rpc_return_value.get_endpoint_instances.return_value
        )

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_get_endpoint_instance(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        instance = self.server.get_endpoint_instance(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.source_environment,
            mock.sentinel.instance_name,
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_ENDPOINT_INSTANCES
                ]
            },
        )

        rpc_return_value = mock_get_worker_service_rpc_for_specs.return_value
        self.assertEqual(
            instance, rpc_return_value.get_endpoint_instance.return_value
        )

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_get_endpoint_source_options(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        options = self.server.get_endpoint_source_options(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.environment,
            mock.sentinel.option_names,
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_SOURCE_ENDPOINT_OPTIONS
                ]
            },
        )

        rpc_return_value = mock_get_worker_service_rpc_for_specs.return_value
        rpc_return_value.get_endpoint_source_options.assert_called_once_with(
            mock.sentinel.context,
            mock_get_endpoint.return_value.type,
            mock_get_endpoint.return_value.connection_info,
            mock.sentinel.environment,
            mock.sentinel.option_names,
        )

        self.assertEqual(
            options, rpc_return_value.get_endpoint_source_options.return_value
        )

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_get_endpoint_destination_options(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        options = self.server.get_endpoint_destination_options(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.environment,
            mock.sentinel.option_names,
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_DESTINATION_ENDPOINT_OPTIONS
                ]
            },
        )

        rpc_return_value = mock_get_worker_service_rpc_for_specs.return_value
        rpc_return_value.get_endpoint_destination_options\
            .assert_called_once_with(
                mock.sentinel.context,
                mock_get_endpoint.return_value.type,
                mock_get_endpoint.return_value.connection_info,
                mock.sentinel.environment,
                mock.sentinel.option_names,
                )

        self.assertEqual(
            options,
            rpc_return_value.get_endpoint_destination_options.return_value,
        )

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_get_endpoint_networks(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        networks = self.server.get_endpoint_networks(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.environment,
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_ENDPOINT_NETWORKS
                ]
            },
        )

        rpc_return_value = mock_get_worker_service_rpc_for_specs.return_value
        rpc_return_value.get_endpoint_networks.assert_called_once_with(
            mock.sentinel.context,
            mock_get_endpoint.return_value.type,
            mock_get_endpoint.return_value.connection_info,
            mock.sentinel.environment,
        )

        self.assertEqual(
            networks, rpc_return_value.get_endpoint_networks.return_value
        )

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_get_endpoint_storage_pools(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        storage_pools = self.server.get_endpoint_storage(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.environment,
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_ENDPOINT_STORAGE
                ]
            },
        )

        rpc_return_value = mock_get_worker_service_rpc_for_specs.return_value
        rpc_return_value.get_endpoint_storage.assert_called_once_with(
            mock.sentinel.context,
            mock_get_endpoint.return_value.type,
            mock_get_endpoint.return_value.connection_info,
            mock.sentinel.environment,
        )

        self.assertEqual(
            storage_pools, rpc_return_value.get_endpoint_storage.return_value
        )

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_validate_endpoint_connection(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        self.server.validate_endpoint_connection(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_ENDPOINT
                ]
            },
        )

        rpc_return_value = mock_get_worker_service_rpc_for_specs.return_value
        rpc_return_value.validate_endpoint_connection.assert_called_once_with(
            mock.sentinel.context,
            mock_get_endpoint.return_value.type,
            mock_get_endpoint.return_value.connection_info,
        )

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_validate_endpoint_target_environment(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        self.server.validate_endpoint_target_environment(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.target_env,
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_ENDPOINT
                ]
            },
        )

        mock_get_worker_service_rpc_for_specs.return_value\
            .validate_endpoint_target_environment.assert_called_once_with(
                mock.sentinel.context,
                mock_get_endpoint.return_value.type,
                mock.sentinel.target_env,
                )

    @mock.patch.object(
        server.ConductorServerEndpoint, "_get_worker_service_rpc_for_specs"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "get_endpoint")
    def test_validate_endpoint_source_environment(
            self, mock_get_endpoint, mock_get_worker_service_rpc_for_specs
    ):
        self.server.validate_endpoint_source_environment(
            mock.sentinel.context,
            mock.sentinel.endpoint_id,
            mock.sentinel.source_env,
        )

        mock_get_endpoint.assert_called_once_with(
            mock.sentinel.context, mock.sentinel.endpoint_id
        )

        mock_get_worker_service_rpc_for_specs.assert_called_once_with(
            mock.sentinel.context,
            enabled=True,
            region_sets=[[]],
            provider_requirements={
                mock_get_endpoint.return_value.type: [
                    constants.PROVIDER_TYPE_ENDPOINT
                ]
            },
        )

        mock_get_worker_service_rpc_for_specs.return_value\
            .validate_endpoint_source_environment.assert_called_once_with(
                mock.sentinel.context,
                mock_get_endpoint.return_value.type,
                mock.sentinel.source_env,
                )

    @mock.patch.object(
        rpc_worker_client.WorkerClient, "from_service_definition"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "_scheduler_client")
    def test_get_available_providers(
            self, mock_scheduler_client, mock_service_definition
    ):
        providers = self.server.get_available_providers(mock.sentinel.context)
        mock_service_definition.assert_called_once_with(
            mock_scheduler_client.get_any_worker_service(mock.sentinel.context)
        )
        mock_service_definition.return_value\
            .get_available_providers.assert_called_once_with(
                mock.sentinel.context
                )
        self.assertEqual(
            providers,
            mock_service_definition
            .return_value.get_available_providers.return_value,
        )

    @mock.patch.object(server.ConductorServerEndpoint, "_scheduler_client")
    @mock.patch.object(
        rpc_worker_client.WorkerClient, "from_service_definition"
    )
    def test_get_provider_schemas(
            self, mock_service_definition, mock_scheduler_client
    ):
        schemas = self.server.get_provider_schemas(
            mock.sentinel.context,
            mock.sentinel.platform_name,
            mock.sentinel.provider_type,
        )
        mock_service_definition.assert_called_once_with(
            mock_scheduler_client.get_any_worker_service(mock.sentinel.context)
        )
        mock_service_definition.return_value\
            .get_provider_schemas.assert_called_once_with(
                mock.sentinel.context,
                mock.sentinel.platform_name,
                mock.sentinel.provider_type,
                )
        self.assertEqual(
            schemas,
            mock_service_definition.return_value
            .get_provider_schemas.return_value,
        )

    @mock.patch.object(models, "Task")
    @mock.patch.object(uuid, "uuid4", return_value="task_id")
    def test_create_task(
            self, mock_uuid4, mock_task_model
    ):  # pylint: disable=unused-argument
        task1 = mock.sentinel.task1
        task1.id = mock.sentinel.task1_id
        task2 = mock.sentinel.task2
        task2.id = "task_id"
        task2.status = constants.TASK_STATUS_SCHEDULED
        execution = mock.sentinel.executions
        execution.tasks = [task1, task2]

        task = self.server._create_task(
            mock.sentinel.instance, mock.sentinel.task_type, execution
        )

        self.assertEqual(task.index, 3)
        self.assertEqual(task.instance, mock.sentinel.instance)
        self.assertEqual(task.status, constants.TASK_STATUS_SCHEDULED)

        # Handles depends_on
        task = self.server._create_task(
            mock.sentinel.instance,
            mock.sentinel.task_type,
            execution,
            depends_on=["task_id"],
            on_error=True,
        )
        self.assertEqual(task.status, constants.TASK_STATUS_SCHEDULED)
        self.assertEqual(task.on_error, True)
        task = self.server._create_task(
            mock.sentinel.instance,
            mock.sentinel.task_type,
            execution,
            depends_on=["other_task"],
            on_error=True,
        )
        self.assertEqual(task.status, constants.TASK_STATUS_ON_ERROR_ONLY)

        # Handles on_error_only
        task = self.server._create_task(
            mock.sentinel.instance,
            mock.sentinel.task_type,
            execution,
            depends_on=["task_id"],
            on_error_only=True,
        )
        self.assertEqual(task.on_error, True)
        self.assertEqual(task.status, constants.TASK_STATUS_ON_ERROR_ONLY)

        # Handles on_error with no depends_on
        task = self.server._create_task(
            mock.sentinel.instance,
            mock.sentinel.task_type,
            execution,
            on_error=True,
        )
        self.assertEqual(task.on_error, True)
        self.assertEqual(task.status, constants.TASK_STATUS_SCHEDULED)

    @mock.patch.object(
        rpc_worker_client.WorkerClient, "from_service_definition"
    )
    @mock.patch.object(db_api, "set_task_status")
    @mock.patch.object(server.ConductorServerEndpoint, "_scheduler_client")
    def test_get_worker_service_rpc_for_task(
            self,
            mock_scheduler_client,
            mock_set_task_status,
            mock_service_definition,
    ):
        task_mock = mock.Mock()
        service = self.server._get_worker_service_rpc_for_task(
            mock.sentinel.context,
            task_mock,
            mock.sentinel.origin_endpoint,
            mock.sentinel.destination_endpoint,
        )
        mock_scheduler_client.get_worker_service_for_task\
            .assert_called_once_with(
                mock.sentinel.context,
                {"id": task_mock.id, "task_type": task_mock.task_type},
                mock.sentinel.origin_endpoint,
                mock.sentinel.destination_endpoint,
                retry_count=5,
                retry_period=2,
                random_choice=True,
                )
        mock_service_definition.assert_called_once_with(
            mock_scheduler_client.get_worker_service_for_task.return_value
        )
        self.assertEqual(service, mock_service_definition.return_value)
        mock_set_task_status.assert_not_called()

        # Handles exception
        mock_scheduler_client.get_worker_service_for_task.side_effect = (
            Exception("test")
        )
        self.assertRaises(
            Exception,
            self.server._get_worker_service_rpc_for_task,
            mock.sentinel.context,
            task_mock,
            mock.sentinel.origin_endpoint,
            mock.sentinel.destination_endpoint,
        )
        mock_set_task_status.assert_called_once_with(
            mock.sentinel.context,
            task_mock.id,
            constants.TASK_STATUS_FAILED_TO_SCHEDULE,
            exception_details="test",
        )

    @mock.patch.object(server.ConductorServerEndpoint, "_create_task")
    @mock.patch.object(
        server.ConductorServerEndpoint, "_check_replica_running_executions"
    )
    @mock.patch.object(server.ConductorServerEndpoint, "_get_replica")
    def test_delete_replica_disks_invalid_state(
            self, mock_get_replica,
            mock_check_replica_running, mock_create_task
    ):
        mock_replica = mock_get_replica.return_value
        mock_replica.instances = [mock.sentinel.instance]
        mock_replica.info = {}
        delete_replica_disks = testutils.get_wrapped_function(
            self.server.delete_replica_disks
        )

        self.assertRaises(
            exception.InvalidReplicaState,
            delete_replica_disks,
            self.server,
            mock.sentinel.context,
            mock.sentinel.replica_id,
        )

        mock_get_replica.assert_called_once_with(
            mock.sentinel.context,
            mock.sentinel.replica_id,
            include_task_info=True,
        )
        mock_check_replica_running.assert_called_once_with(
            mock.sentinel.context, mock_replica
        )
        mock_create_task.assert_not_called()

    @ddt.file_data("data/execution_tasks_config.yml")
    @ddt.unpack
    def test_check_execution_tasks_sanity(
            self, tasks_config, init_task_info, expected_result
    ):
        def convert_to_task(task_config):
            instance_task = mock.Mock()
            instance_task.instance = task_config.get(
                "instance", mock.sentinel.instance
            )
            instance_task.id = task_config.get("id", str(uuid.uuid4()))
            instance_task.status = task_config.get(
                "status", constants.TASK_STATUS_SCHEDULED
            )
            instance_task.depends_on = task_config.get("depends_on", None)
            instance_task.task_type = task_config.get(
                "task_type",
                constants.TASK_TYPE_DEPLOY_MIGRATION_SOURCE_RESOURCES,
            )
            return instance_task

        execution = mock.sentinel.execution
        execution.id = str(uuid.uuid4())
        execution.type = mock.sentinel.execution_type

        execution.tasks = [convert_to_task(t) for t in tasks_config]

        if init_task_info is not None:
            initial_task_info = init_task_info
        else:
            initial_task_info = {
                mock.sentinel.instance: {
                    "source_environment": mock.sentinel.source_environment,
                    "export_info": mock.sentinel.export_info,
                }
            }

        if not expected_result:
            self.server._check_execution_tasks_sanity(
                execution, initial_task_info
            )
        else:
            exception_mappings = {
                "INVALID_STATE": exception.InvalidTaskState,
                "MISSING_PARAMS": exception.TaskParametersException,
                "MISSING_DEPENDENCIES": exception.TaskDependencyException,
                "FIELDS_CONFLICT": exception.TaskFieldsConflict,
                "DEADLOCK": exception.ExecutionDeadlockException,
            }
            with self.assertRaisesRegex(
                exception_mappings[expected_result["type"]],
                expected_result.get("message", ""),
            ):
                self.server._check_execution_tasks_sanity(
                    execution, initial_task_info
                )
