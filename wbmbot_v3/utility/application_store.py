import hashlib
import os
from abc import ABC, abstractmethod
from typing import Any

from wbmbot_v3.helpers import constants
from wbmbot_v3.logger import wbm_logger
from wbmbot_v3.utility import firestore_support, io_operations, misc_operations

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
color_me = wbm_logger.ColoredLogger(__appname__)
LOG = color_me.create_logger()


class ApplicationStore(ABC):
    def initialize(self) -> None:
        return None

    @abstractmethod
    def has_applied(self, email: str, flat_obj) -> bool:
        raise NotImplementedError

    @abstractmethod
    def record_application(self, email: str, flat_obj) -> None:
        raise NotImplementedError


class CompositeApplicationStore(ApplicationStore):
    def __init__(self, stores, label: str | None = None):
        self.stores = [store for store in (stores or []) if store]
        self.label = label or "composite"

    def initialize(self) -> None:
        for store in self.stores:
            store.initialize()
        LOG.info(
            color_me.cyan(
                f"Using composite application store ({self.label}, stores={len(self.stores)}) 🧩"
            )
        )

    def has_applied(self, email: str, flat_obj) -> bool:
        for store in self.stores:
            try:
                if store.has_applied(email, flat_obj):
                    return True
            except Exception as exc:
                LOG.error(
                    color_me.red(
                        f"Application store read failed ({type(store).__name__}): {exc}"
                    )
                )
        return False

    def record_application(self, email: str, flat_obj) -> None:
        for store in self.stores:
            try:
                store.record_application(email, flat_obj)
            except Exception as exc:
                LOG.error(
                    color_me.red(
                        f"Application store write failed ({type(store).__name__}): {exc}"
                    )
                )


class FileApplicationStore(ApplicationStore):
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path

    def initialize(self) -> None:
        io_operations.initialize_application_logger(self.log_file_path)

    def has_applied(self, email: str, flat_obj) -> bool:
        return io_operations.check_flat_already_applied(
            self.log_file_path, email, flat_obj
        )

    def record_application(self, email: str, flat_obj) -> None:
        io_operations.write_log_file(self.log_file_path, email, flat_obj)


class FirestoreApplicationStore(ApplicationStore):
    def __init__(
        self,
        project_id: str | None = None,
        collection: str | None = None,
        credentials_path: str | None = None,
        database: str | None = None,
    ):
        self.project_id = project_id
        self.collection_name = collection or "wbm_applications"
        self.credentials_path = credentials_path
        self.database = database
        self._client: Any | None = None
        self._collection: Any | None = None
        self._google_api_error: type[Exception] | None = None

    def initialize(self) -> None:
        self._client, self._google_api_error = firestore_support.create_firestore_client(
            project_id=self.project_id,
            database=self.database,
            credentials_path=self.credentials_path,
        )
        self._collection = self._client.collection(self.collection_name)

        LOG.info(
            color_me.cyan(
                "Using Firestore application store "
                f"(project={self._client.project}, "
                f"collection={self.collection_name}) 🔥"
            )
        )

    @staticmethod
    def _normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    @classmethod
    def _doc_id(cls, email: str, flat_hash: str) -> str:
        normalized_email = cls._normalize_email(email)
        digest = hashlib.sha256(f"{normalized_email}|{flat_hash}".encode("utf-8"))
        return digest.hexdigest()

    @staticmethod
    def _build_entry(email: str, flat_obj) -> dict:
        applied_date = constants.current_date().isoformat()
        street = flat_obj.street
        zip_code = flat_obj.zip_code
        return {
            "email": (email or "").strip(),
            "flat_hash": flat_obj.hash,
            "date": applied_date,
            "applied_on": applied_date,
            "title": flat_obj.title,
            "street": street,
            "zip_code": zip_code,
            "address": f"{street} {zip_code}".strip(),
            "rent": misc_operations.convert_rent(flat_obj.total_rent),
            "size": misc_operations.convert_size(flat_obj.size),
            "rooms": misc_operations.get_zimmer_count(flat_obj.rooms),
            "wbs?": flat_obj.wbs,
            "created_at": constants.utc_now().isoformat(),
        }

    def _require_collection(self):
        if not self._collection:
            raise RuntimeError("Firestore store not initialized.")
        return self._collection

    def _require_google_api_error(self) -> type[Exception]:
        if self._google_api_error is None:
            raise RuntimeError("Firestore store not initialized.")
        return self._google_api_error

    def has_applied(self, email: str, flat_obj) -> bool:
        collection = self._require_collection()
        google_api_error = self._require_google_api_error()
        doc_id = self._doc_id(email, flat_obj.hash)
        try:
            return bool(collection.document(doc_id).get().exists)
        except google_api_error as exc:
            LOG.error(color_me.red(f"Firestore read failed: {exc}"))
            raise

    def record_application(self, email: str, flat_obj) -> None:
        collection = self._require_collection()
        google_api_error = self._require_google_api_error()
        doc_id = self._doc_id(email, flat_obj.hash)
        payload = self._build_entry(email, flat_obj)
        try:
            collection.document(doc_id).set(payload, merge=True)
            LOG.info(
                color_me.green(
                    "Recorded application in Firestore "
                    f"(doc={doc_id}, email={payload.get('email')}) ✅"
                )
            )
        except google_api_error as exc:
            LOG.error(color_me.red(f"Firestore write failed: {exc}"))
            raise


def build_application_store(
    backend: str,
    log_file_path: str,
    project_id: str | None = None,
    collection: str | None = None,
    credentials_path: str | None = None,
    database: str | None = None,
) -> ApplicationStore:
    backend = (backend or "file").strip().lower()
    if backend == "firestore":
        return FirestoreApplicationStore(
            project_id=project_id,
            collection=collection,
            credentials_path=credentials_path,
            database=database,
        )
    return FileApplicationStore(log_file_path)
