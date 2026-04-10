from unittest.mock import Mock, patch

from wbmbot_v3.utility.application_store import FirestoreApplicationStore
from wbmbot_v3.utility.config_store import FirestoreConfigStore


def test_application_store_initialize_uses_shared_firestore_client():
    mock_client = Mock()
    mock_collection = Mock()
    mock_client.collection.return_value = mock_collection

    with patch(
        "wbmbot_v3.utility.application_store.firestore_support.create_firestore_client",
        return_value=(mock_client, RuntimeError),
    ) as create_client:
        store = FirestoreApplicationStore(
            project_id="project-1",
            collection="applications",
            credentials_path="/tmp/service-account.json",
            database="wbm-db",
        )
        store.initialize()

    create_client.assert_called_once_with(
        project_id="project-1",
        database="wbm-db",
        credentials_path="/tmp/service-account.json",
    )
    assert store._collection is mock_collection


def test_config_store_initialize_uses_shared_firestore_client():
    mock_client = Mock()
    mock_collection = Mock()
    mock_client.collection.return_value = mock_collection

    with patch(
        "wbmbot_v3.utility.config_store.firestore_support.create_firestore_client",
        return_value=(mock_client, RuntimeError),
    ) as create_client:
        store = FirestoreConfigStore(
            project_id="project-1",
            collection="users",
            credentials_path="/tmp/service-account.json",
            database="wbm-db",
        )
        store.initialize()

    create_client.assert_called_once_with(
        project_id="project-1",
        database="wbm-db",
        credentials_path="/tmp/service-account.json",
    )
    assert store._collection is mock_collection
