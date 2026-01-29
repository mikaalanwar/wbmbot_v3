import os
import sys
import tempfile
import unittest
import uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "wbmbot_v3"))

from utility.application_store import (  # noqa: E402
    FileApplicationStore,
    FirestoreApplicationStore,
    build_application_store,
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


if __name__ == "__main__":
    unittest.main()
