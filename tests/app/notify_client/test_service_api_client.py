from unittest.mock import Mock, call
from uuid import uuid4

import pytest

from app import invite_api_client, service_api_client, user_api_client
from app.notify_client.service_api_client import ServiceAPIClient
from tests.conftest import SERVICE_ONE_ID

FAKE_TEMPLATE_ID = uuid4()


def test_client_posts_archived_true_when_deleting_template(mocker):
    mocker.patch("app.notify_client.current_user", id="1")
    mock_redis_delete_by_pattern = mocker.patch("app.extensions.RedisClient.delete_by_pattern")
    expected_data = {"archived": True, "created_by": "1"}
    expected_url = f"/service/{SERVICE_ONE_ID}/template/{FAKE_TEMPLATE_ID}"

    client = ServiceAPIClient()
    mock_post = mocker.patch("app.notify_client.service_api_client.ServiceAPIClient.post")
    mocker.patch(
        "app.notify_client.service_api_client.ServiceAPIClient.get",
        return_value={"data": {"id": str(FAKE_TEMPLATE_ID)}},
    )

    client.delete_service_template(SERVICE_ONE_ID, FAKE_TEMPLATE_ID)
    mock_post.assert_called_once_with(expected_url, data=expected_data)
    assert call(f"service-{SERVICE_ONE_ID}-template-*") in mock_redis_delete_by_pattern.call_args_list


def test_client_gets_service(mocker):
    client = ServiceAPIClient()
    mock_get = mocker.patch.object(client, "get", return_value={})

    client.get_service("foo")
    mock_get.assert_called_once_with("/service/foo")


@pytest.mark.parametrize("limit_days", [None, 30])
def test_client_gets_service_statistics(mocker, limit_days):
    client = ServiceAPIClient()
    mock_get = mocker.patch.object(client, "get", return_value={"data": {"a": "b"}})

    ret = client.get_service_statistics("foo", limit_days)

    assert ret == {"a": "b"}
    mock_get.assert_called_once_with("/service/foo/statistics", params={"limit_days": limit_days})


def test_client_only_updates_allowed_attributes(mocker):
    mocker.patch("app.notify_client.current_user", id="1")
    with pytest.raises(TypeError) as error:
        ServiceAPIClient().update_service("service_id", foo="bar")
    assert str(error.value) == "Not allowed to update service attributes: foo"


def test_client_creates_service_with_correct_data(
    mocker,
    active_user_with_permissions,
    fake_uuid,
):
    client = ServiceAPIClient()
    mock_post = mocker.patch.object(client, "post", return_value={"data": {"id": None}})
    mocker.patch("app.notify_client.current_user", id="123")

    client.create_service(
        "My first service",
        "central_government",
        1,
        1,
        1,
        True,
        fake_uuid,
        "test@example.com",
    )
    mock_post.assert_called_once_with(
        "/service",
        dict(
            # Autogenerated arguments
            created_by="123",
            active=True,
            # ‘service_name’ argument is coerced to ‘name’
            name="My first service",
            # The rest pass through with the same names
            organisation_type="central_government",
            email_message_limit=1,
            sms_message_limit=1,
            letter_message_limit=1,
            restricted=True,
            user_id=fake_uuid,
            email_from="test@example.com",
        ),
    )


def test_get_precompiled_template(mocker):
    client = ServiceAPIClient()
    mock_get = mocker.patch.object(client, "get")

    client.get_precompiled_template(SERVICE_ONE_ID)
    mock_get.assert_called_once_with(f"/service/{SERVICE_ONE_ID}/template/precompiled")


@pytest.mark.parametrize(
    "template_data, extra_args, expected_count",
    (
        (
            [],
            {},
            0,
        ),
        (
            [],
            {"template_type": "email"},
            0,
        ),
        (
            [
                {"template_type": "email"},
                {"template_type": "sms"},
            ],
            {},
            2,
        ),
        (
            [
                {"template_type": "email"},
                {"template_type": "sms"},
            ],
            {"template_type": "email"},
            1,
        ),
        (
            [
                {"template_type": "email"},
                {"template_type": "sms"},
            ],
            {"template_type": "letter"},
            0,
        ),
    ),
)
def test_client_returns_count_of_service_templates(
    notify_admin,
    mocker,
    template_data,
    extra_args,
    expected_count,
):

    mocker.patch("app.service_api_client.get_service_templates", return_value={"data": template_data})

    assert service_api_client.count_service_templates(SERVICE_ONE_ID, **extra_args) == expected_count


@pytest.mark.parametrize(
    (
        "client_method,"
        "extra_args,"
        "expected_cache_get_calls,"
        "cache_value,"
        "expected_api_calls,"
        "expected_cache_set_calls,"
        "expected_return_value,"
    ),
    [
        (
            service_api_client.get_service,
            [SERVICE_ONE_ID],
            [call(f"service-{SERVICE_ONE_ID}")],
            b'{"data_from": "cache"}',
            [],
            [],
            {"data_from": "cache"},
        ),
        (
            service_api_client.get_service,
            [SERVICE_ONE_ID],
            [call(f"service-{SERVICE_ONE_ID}")],
            None,
            [call(f"/service/{SERVICE_ONE_ID}")],
            [
                call(
                    f"service-{SERVICE_ONE_ID}",
                    '{"data_from": "api"}',
                    ex=604800,
                )
            ],
            {"data_from": "api"},
        ),
        (
            service_api_client.get_service_template,
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID],
            [call(f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-version-None")],
            b'{"data_from": "cache"}',
            [],
            [],
            {"data_from": "cache"},
        ),
        (
            service_api_client.get_service_template,
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID],
            [
                call(f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-version-None"),
            ],
            None,
            [call(f"/service/{SERVICE_ONE_ID}/template/{FAKE_TEMPLATE_ID}")],
            [
                call(
                    f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-version-None",
                    '{"data_from": "api"}',
                    ex=604800,
                ),
            ],
            {"data_from": "api"},
        ),
        (
            service_api_client.get_service_template,
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID, 1],
            [call(f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-version-1")],
            b'{"data_from": "cache"}',
            [],
            [],
            {"data_from": "cache"},
        ),
        (
            service_api_client.get_service_template,
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID, 1],
            [
                call(f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-version-1"),
            ],
            None,
            [call(f"/service/{SERVICE_ONE_ID}/template/{FAKE_TEMPLATE_ID}/version/1")],
            [
                call(
                    f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-version-1",
                    '{"data_from": "api"}',
                    ex=604800,
                ),
            ],
            {"data_from": "api"},
        ),
        (
            service_api_client.get_service_templates,
            [SERVICE_ONE_ID],
            [call(f"service-{SERVICE_ONE_ID}-templates")],
            b'{"data_from": "cache"}',
            [],
            [],
            {"data_from": "cache"},
        ),
        (
            service_api_client.get_service_templates,
            [SERVICE_ONE_ID],
            [call(f"service-{SERVICE_ONE_ID}-templates")],
            None,
            [call(f"/service/{SERVICE_ONE_ID}/template?detailed=False")],
            [
                call(
                    f"service-{SERVICE_ONE_ID}-templates",
                    '{"data_from": "api"}',
                    ex=604800,
                )
            ],
            {"data_from": "api"},
        ),
        (
            service_api_client.get_service_template_versions,
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID],
            [call(f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-versions")],
            b'{"data_from": "cache"}',
            [],
            [],
            {"data_from": "cache"},
        ),
        (
            service_api_client.get_service_template_versions,
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID],
            [
                call(f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-versions"),
            ],
            None,
            [call(f"/service/{SERVICE_ONE_ID}/template/{FAKE_TEMPLATE_ID}/versions")],
            [
                call(
                    f"service-{SERVICE_ONE_ID}-template-{FAKE_TEMPLATE_ID}-versions",
                    '{"data_from": "api"}',
                    ex=604800,
                ),
            ],
            {"data_from": "api"},
        ),
        (
            service_api_client.get_returned_letter_summary,
            [SERVICE_ONE_ID],
            [call(f"service-{SERVICE_ONE_ID}-returned-letters-summary")],
            None,
            [call(f"service/{SERVICE_ONE_ID}/returned-letter-summary")],
            [
                call(
                    f"service-{SERVICE_ONE_ID}-returned-letters-summary",
                    '{"data_from": "api"}',
                    ex=604800,
                )
            ],
            {"data_from": "api"},
        ),
        (
            service_api_client.get_returned_letter_statistics,
            [SERVICE_ONE_ID],
            [call(f"service-{SERVICE_ONE_ID}-returned-letters-statistics")],
            None,
            [call(f"service/{SERVICE_ONE_ID}/returned-letter-statistics")],
            [
                call(
                    f"service-{SERVICE_ONE_ID}-returned-letters-statistics",
                    '{"data_from": "api"}',
                    ex=604800,
                )
            ],
            {"data_from": "api"},
        ),
    ],
)
def test_returns_value_from_cache(
    mocker,
    client_method,
    extra_args,
    expected_cache_get_calls,
    cache_value,
    expected_return_value,
    expected_api_calls,
    expected_cache_set_calls,
):

    mock_redis_get = mocker.patch(
        "app.extensions.RedisClient.get",
        return_value=cache_value,
    )
    mock_api_get = mocker.patch(
        "app.notify_client.NotifyAdminAPIClient.get",
        return_value={"data_from": "api"},
    )
    mock_redis_set = mocker.patch(
        "app.extensions.RedisClient.set",
    )

    assert client_method(*extra_args) == expected_return_value

    assert mock_redis_get.call_args_list == expected_cache_get_calls
    assert mock_api_get.call_args_list == expected_api_calls
    assert mock_redis_set.call_args_list == expected_cache_set_calls


@pytest.mark.parametrize(
    "client, method, extra_args, extra_kwargs",
    [
        (service_api_client, "update_service", [SERVICE_ONE_ID], {"name": "foo"}),
        (service_api_client, "update_service_with_properties", [SERVICE_ONE_ID], {"properties": {}}),
        (service_api_client, "archive_service", [SERVICE_ONE_ID, []], {}),
        (service_api_client, "remove_user_from_service", [SERVICE_ONE_ID, ""], {}),
        (service_api_client, "update_guest_list", [SERVICE_ONE_ID, {}], {}),
        (service_api_client, "create_service_inbound_api", [SERVICE_ONE_ID] + [""] * 3, {}),
        (service_api_client, "update_service_inbound_api", [SERVICE_ONE_ID] + [""] * 4, {}),
        (service_api_client, "add_reply_to_email_address", [SERVICE_ONE_ID, ""], {}),
        (service_api_client, "update_reply_to_email_address", [SERVICE_ONE_ID] + [""] * 2, {}),
        (service_api_client, "delete_reply_to_email_address", [SERVICE_ONE_ID, ""], {}),
        (service_api_client, "add_letter_contact", [SERVICE_ONE_ID, ""], {}),
        (service_api_client, "update_letter_contact", [SERVICE_ONE_ID] + [""] * 2, {}),
        (service_api_client, "delete_letter_contact", [SERVICE_ONE_ID, ""], {}),
        (service_api_client, "add_sms_sender", [SERVICE_ONE_ID, ""], {}),
        (service_api_client, "update_sms_sender", [SERVICE_ONE_ID] + [""] * 2, {}),
        (service_api_client, "delete_sms_sender", [SERVICE_ONE_ID, ""], {}),
        (service_api_client, "update_service_callback_api", [SERVICE_ONE_ID] + [""] * 4, {}),
        (service_api_client, "create_service_callback_api", [SERVICE_ONE_ID] + [""] * 3, {}),
        (service_api_client, "set_service_broadcast_settings", [SERVICE_ONE_ID, "training", "severe", "all", []], {}),
        (user_api_client, "add_user_to_service", [SERVICE_ONE_ID, uuid4(), [], []], {}),
        (invite_api_client, "accept_invite", [SERVICE_ONE_ID, uuid4()], {}),
    ],
)
def test_deletes_service_cache(
    notify_admin,
    mock_get_user,
    mock_get_service_templates,
    mocker,
    client,
    method,
    extra_args,
    extra_kwargs,
):
    mocker.patch("app.notify_client.current_user", id="1")
    mock_redis_delete = mocker.patch("app.extensions.RedisClient.delete")
    mock_request = mocker.patch("notifications_python_client.base.BaseAPIClient.request")

    getattr(client, method)(*extra_args, **extra_kwargs)

    assert call(f"service-{SERVICE_ONE_ID}") in mock_redis_delete.call_args_list
    assert len(mock_request.call_args_list) == 1


@pytest.mark.parametrize(
    "method, extra_args, extra_kwargs, expected_cache_deletes",
    [
        (
            "create_service_template",
            ["name", "type_", "content", SERVICE_ONE_ID],
            {},
            [
                f"service-{SERVICE_ONE_ID}-templates",
            ],
        ),
        (
            "update_service_template",
            [],
            {
                "name": "foo",
                "content": "bar",
                "service_id": SERVICE_ONE_ID,
                "template_id": FAKE_TEMPLATE_ID,
            },
            [
                f"service-{SERVICE_ONE_ID}-templates",
            ],
        ),
        (
            "redact_service_template",
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID],
            {},
            [
                f"service-{SERVICE_ONE_ID}-templates",
            ],
        ),
        (
            "update_service_template_sender",
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID, "foo"],
            {},
            [
                f"service-{SERVICE_ONE_ID}-templates",
            ],
        ),
        (
            "update_service_template_postage",
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID, "first"],
            {},
            [
                f"service-{SERVICE_ONE_ID}-templates",
            ],
        ),
        (
            "delete_service_template",
            [SERVICE_ONE_ID, FAKE_TEMPLATE_ID],
            {},
            [
                f"service-{SERVICE_ONE_ID}-templates",
            ],
        ),
        (
            "archive_service",
            [SERVICE_ONE_ID, []],
            {},
            [
                f"service-{SERVICE_ONE_ID}-templates",
                f"service-{SERVICE_ONE_ID}",
            ],
        ),
    ],
)
def test_deletes_caches_when_modifying_templates(
    notify_admin,
    mock_get_user,
    mocker,
    method,
    extra_args,
    extra_kwargs,
    expected_cache_deletes,
):
    mocker.patch("app.notify_client.current_user", id="1")
    mock_redis_delete = mocker.patch("app.extensions.RedisClient.delete")
    mock_redis_delete_by_pattern = mocker.patch("app.extensions.RedisClient.delete_by_pattern")
    mock_request = mocker.patch("notifications_python_client.base.BaseAPIClient.request")

    getattr(service_api_client, method)(*extra_args, **extra_kwargs)

    assert mock_redis_delete.call_args_list == [call(x) for x in expected_cache_deletes]
    assert len(mock_request.call_args_list) == 1
    if method != "create_service_template":
        # no deletes for template cach on create_service_template
        assert len(mock_redis_delete_by_pattern.call_args_list) == 1
        assert mock_redis_delete_by_pattern.call_args_list[0] == call(f"service-{SERVICE_ONE_ID}-template-*")


def test_deletes_cached_users_when_archiving_service(mocker, mock_get_service_templates):
    mock_redis_delete = mocker.patch("app.extensions.RedisClient.delete")
    mock_redis_delete_by_pattern = mocker.patch("app.extensions.RedisClient.delete_by_pattern")

    mocker.patch("notifications_python_client.base.BaseAPIClient.request", return_value={"data": ""})

    service_api_client.archive_service(SERVICE_ONE_ID, ["my-user-id1", "my-user-id2"])

    assert call("user-my-user-id1", "user-my-user-id2") in mock_redis_delete.call_args_list
    assert call(f"service-{SERVICE_ONE_ID}-template-*") in mock_redis_delete_by_pattern.call_args_list


def test_deletes_cached_users_when_changing_broadcast_service_settings(mocker):
    mock_redis_delete = mocker.patch("app.extensions.RedisClient.delete")

    mocker.patch("notifications_python_client.base.BaseAPIClient.request", return_value={"data": ""})

    service_api_client.set_service_broadcast_settings(
        SERVICE_ONE_ID, "live", "severe", "all", ["my-user-id1", "my-user-id2"]
    )

    assert mock_redis_delete.call_args_list == [
        call("user-my-user-id1", "user-my-user-id2"),
        call(f"service-{SERVICE_ONE_ID}"),
    ]


def test_client_gets_guest_list(mocker):
    client = ServiceAPIClient()
    mock_get = mocker.patch.object(client, "get", return_value=["a", "b", "c"])

    response = client.get_guest_list("foo")

    assert response == ["a", "b", "c"]
    mock_get.assert_called_once_with(
        "/service/foo/guest-list",
    )


def test_client_updates_guest_list(mocker):
    client = ServiceAPIClient()
    mock_put = mocker.patch.object(client, "put")

    client.update_guest_list("foo", data=["a", "b", "c"])

    mock_put.assert_called_once_with(
        "/service/foo/guest-list",
        data=["a", "b", "c"],
    )


def test_client_doesnt_delete_service_template_cache_when_none_exist(
    notify_admin, mock_get_user, mock_get_service_templates_when_no_templates_exist, mocker
):
    mocker.patch("app.notify_client.current_user", id="1")
    mocker.patch("notifications_python_client.base.BaseAPIClient.request")
    mock_redis_delete = mocker.patch("app.extensions.RedisClient.delete")
    mock_redis_delete_by_pattern = mocker.patch("app.extensions.RedisClient.delete_by_pattern")

    service_api_client.update_reply_to_email_address(SERVICE_ONE_ID, uuid4(), "foo@bar.com")

    assert len(mock_redis_delete.call_args_list) == 1
    assert mock_redis_delete.call_args_list[0] == call(f"service-{SERVICE_ONE_ID}")

    assert len(mock_redis_delete_by_pattern.call_args_list) == 1


def test_client_deletes_service_template_cache_when_service_is_updated(notify_admin, mock_get_user, mocker):
    mocker.patch("app.notify_client.current_user", id="1")
    mocker.patch("notifications_python_client.base.BaseAPIClient.request")
    mock_redis_delete = mocker.patch("app.extensions.RedisClient.delete")
    mock_redis_delete_by_pattern = mocker.patch("app.extensions.RedisClient.delete_by_pattern")

    service_api_client.update_reply_to_email_address(SERVICE_ONE_ID, uuid4(), "foo@bar.com")

    assert len(mock_redis_delete.call_args_list) == 1
    assert mock_redis_delete.call_args_list[0] == call(f"service-{SERVICE_ONE_ID}")
    assert mock_redis_delete_by_pattern.call_args_list[0] == call(f"service-{SERVICE_ONE_ID}-template-*")


def test_client_updates_service_with_allowed_attributes(
    mocker,
):
    client = ServiceAPIClient()
    mock_post = mocker.patch.object(client, "post", return_value={"data": {"id": None}})
    mocker.patch("app.notify_client.current_user", id="123")

    allowed_attributes = [
        "active",
        "consent_to_research",
        "contact_link",
        "count_as_live",
        "email_branding",
        "email_from",
        "free_sms_fragment_limit",
        "go_live_at",
        "go_live_user",
        "letter_branding",
        "letter_contact_block",
        "name",
        "notes",
        "organisation_type",
        "permissions",
        "prefix_sms",
        "rate_limit",
        "reply_to_email_address",
        "restricted",
        "sms_sender",
        "volume_email",
        "volume_letter",
        "volume_sms",
    ]

    attrs_dict = {}
    for attr in allowed_attributes:
        attrs_dict[attr] = "value"

    client.update_service(SERVICE_ONE_ID, **attrs_dict)
    mock_post.assert_called_once_with(f"/service/{SERVICE_ONE_ID}", {**{"created_by": "123"}, **attrs_dict})


@pytest.mark.parametrize(
    "err_data, expected_message",
    (
        ({"name": "Service name error"}, "This service name is already in use"),
        (
            {"email_from": "email_from disallowed characters"},
            "Service name must not include characters from a non-Latin alphabet",
        ),
        ({"other": "blah"}, None),
    ),
)
def test_client_parsing_service_name_errors(err_data, expected_message):
    client = ServiceAPIClient()
    error = Mock()
    error.message = err_data

    error_message = client.parse_edit_service_http_error(error)

    assert error_message == expected_message
