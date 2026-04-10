import os
import tempfile
import unittest
import uuid

from wbmbot_v3.utility.application_store import (
    CompositeApplicationStore,
    FileApplicationStore,
    FirestoreApplicationStore,
    build_application_store,
)
from wbmbot_v3.utility.config_store import (
    FileConfigStore,
    FirestoreConfigStore,
    build_config_store,
)


class DummyFlat:
    def __init__(self, hash_value: str):
        self.hash = hash_value
        self.title = "Test Flat"
        self.street = "Teststr 1"
        self.zip_code = "10115"
        self.total_rent = "1234"
        self.size = "55"
        self.rooms = "2"
        self.wbs = False


class FileApplicationStoreTests(unittest.TestCase):
    def test_file_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "successful_applications.json")
            store = FileApplicationStore(log_path)
            store.initialize()

            email = "user@example.com"
            flat = DummyFlat(hash_value="hash-123")

            self.assertFalse(store.has_applied(email, flat))
            store.record_application(email, flat)
            self.assertTrue(store.has_applied(email, flat))
            self.assertTrue(os.path.isfile(log_path))

    def test_build_store_defaults_to_file(self):
        store = build_application_store("file", "/tmp/does-not-matter.json")
        self.assertIsInstance(store, FileApplicationStore)

    def test_build_store_supports_firestore_backend(self):
        store = build_application_store("firestore", "/tmp/does-not-matter.json")
        self.assertIsInstance(store, FirestoreApplicationStore)

    def test_build_config_store_defaults_to_file(self):
        store = build_config_store("file", "/tmp/wbm_config.json")
        self.assertIsInstance(store, FileConfigStore)

    def test_build_config_store_supports_firestore_backend(self):
        store = build_config_store("firestore", "/tmp/wbm_config.json")
        self.assertIsInstance(store, FirestoreConfigStore)


class CompositeApplicationStoreTests(unittest.TestCase):
    def test_composite_checks_all_stores(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path_one = os.path.join(temp_dir, "one.json")
            log_path_two = os.path.join(temp_dir, "two.json")

            store_one = FileApplicationStore(log_path_one)
            store_two = FileApplicationStore(log_path_two)
            composite = CompositeApplicationStore([store_one, store_two])
            composite.initialize()

            email = "composite@example.com"
            flat = DummyFlat(hash_value="hash-composite")

            self.assertFalse(composite.has_applied(email, flat))
            composite.record_application(email, flat)
            self.assertTrue(composite.has_applied(email, flat))
            self.assertTrue(store_one.has_applied(email, flat))
            self.assertTrue(store_two.has_applied(email, flat))


class FirestoreApplicationStoreTests(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("RUN_FIRESTORE_TESTS") == "1",
        "Firestore integration tests disabled (set RUN_FIRESTORE_TESTS=1).",
    )
    def test_firestore_connectivity(self):
        project_id = os.getenv("FIRESTORE_PROJECT_ID")
        if not project_id:
            self.skipTest("FIRESTORE_PROJECT_ID is required.")

        collection = os.getenv("FIRESTORE_TEST_COLLECTION") or os.getenv(
            "FIRESTORE_COLLECTION", "wbm_applications_test"
        )
        database = os.getenv("FIRESTORE_DATABASE")
        credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        store = FirestoreApplicationStore(
            project_id=project_id,
            collection=collection,
            credentials_path=credentials,
            database=database,
        )
        store.initialize()

        email = "integration-test@example.com"
        flat_hash = uuid.uuid4().hex
        flat = DummyFlat(hash_value=flat_hash)

        self.assertFalse(store.has_applied(email, flat))
        store.record_application(email, flat)
        self.assertTrue(store.has_applied(email, flat))

        if os.getenv("KEEP_FIRESTORE_TEST_DOCS") != "1":
            try:
                doc_id = store._doc_id(email, flat_hash)
                store._collection.document(doc_id).delete()
            except Exception:
                pass


class FirestoreEntryTests(unittest.TestCase):
    def test_build_entry_includes_address_and_applied_on(self):
        email = "user@example.com"
        flat = DummyFlat(hash_value="hash-entry")
        entry = FirestoreApplicationStore._build_entry(email, flat)

        self.assertEqual(entry["email"], email)
        self.assertEqual(entry["flat_hash"], flat.hash)
        self.assertIn("applied_on", entry)
        self.assertEqual(entry["applied_on"], entry["date"])
        self.assertIn("address", entry)
        self.assertIn(flat.street, entry["address"])
        self.assertIn(flat.zip_code, entry["address"])


if __name__ == "__main__":
    unittest.main()
