import datetime as dt
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import os
import sys
from typing import Optional

from helpers import constants
from logger import wbm_logger
from utility import io_operations, misc_operations

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
color_me = wbm_logger.ColoredLogger(__appname__)
LOG = color_me.create_logger()

_FIRESTORE = None
_GOOGLE_API_ERROR = None


def _patch_protobuf_imports_for_py314() -> None:
    """
    Work around protobuf C-extension import failures on Python 3.14 by forcing
    ImportError for the extension modules so protobuf falls back to pure Python.
    """

    if sys.version_info < (3, 14):
        return

    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

    blocked_prefixes = ("google._upb", "google.protobuf.pyext")

    if not any(
        getattr(finder, "_wbm_blocker", False) for finder in sys.meta_path
    ):

        class _BlockUpbLoader(importlib.abc.Loader):
            def create_module(self, spec):
                return None

            def exec_module(self, module):
                raise ImportError(module.__name__)

        class _BlockUpbFinder(importlib.abc.MetaPathFinder):
            _wbm_blocker = True

            def find_spec(self, fullname, path, target=None):
                if fullname.startswith(blocked_prefixes):
                    return importlib.machinery.ModuleSpec(
                        fullname, _BlockUpbLoader()
                    )
                return None

        sys.meta_path.insert(0, _BlockUpbFinder())


class ApplicationStore:
    def initialize(self) -> None:
        return None

    def has_applied(self, email: str, flat_obj) -> bool:
        raise NotImplementedError

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
        project_id: Optional[str] = None,
        collection: Optional[str] = None,
        credentials_path: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.project_id = project_id
        self.collection_name = collection or "wbm_applications"
        self.credentials_path = credentials_path
        self.database = database
        self._client = None
        self._collection = None

    def initialize(self) -> None:
        if self.credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path

        _patch_protobuf_imports_for_py314()

        global _FIRESTORE, _GOOGLE_API_ERROR
        if _FIRESTORE is None or _GOOGLE_API_ERROR is None:
            from google.api_core.exceptions import GoogleAPIError
            from google.cloud import firestore

            _FIRESTORE = firestore
            _GOOGLE_API_ERROR = GoogleAPIError

        if self.database:
            self._client = _FIRESTORE.Client(
                project=self.project_id, database=self.database
            )
        else:
            self._client = _FIRESTORE.Client(project=self.project_id)

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
        street = flat_obj.street
        zip_code = flat_obj.zip_code
        return {
            "email": (email or "").strip(),
            "flat_hash": flat_obj.hash,
            "date": constants.today.isoformat(),
            "applied_on": constants.today.isoformat(),
            "title": flat_obj.title,
            "street": street,
            "zip_code": zip_code,
            "address": f"{street} {zip_code}".strip(),
            "rent": misc_operations.convert_rent(flat_obj.total_rent),
            "size": misc_operations.convert_size(flat_obj.size),
            "rooms": misc_operations.get_zimmer_count(flat_obj.rooms),
            "wbs?": flat_obj.wbs,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    def has_applied(self, email: str, flat_obj) -> bool:
        if not self._collection:
            raise RuntimeError("Firestore store not initialized.")
        doc_id = self._doc_id(email, flat_obj.hash)
        try:
            return bool(self._collection.document(doc_id).get().exists)
        except _GOOGLE_API_ERROR as exc:
            LOG.error(color_me.red(f"Firestore read failed: {exc}"))
            raise

    def record_application(self, email: str, flat_obj) -> None:
        if not self._collection:
            raise RuntimeError("Firestore store not initialized.")
        doc_id = self._doc_id(email, flat_obj.hash)
        payload = self._build_entry(email, flat_obj)
        try:
            self._collection.document(doc_id).set(payload, merge=True)
            LOG.info(
                color_me.green(
                    "Recorded application in Firestore "
                    f"(doc={doc_id}, email={payload.get('email')}) ✅"
                )
            )
        except _GOOGLE_API_ERROR as exc:
            LOG.error(color_me.red(f"Firestore write failed: {exc}"))
            raise


def build_application_store(
    backend: str,
    log_file_path: str,
    project_id: Optional[str] = None,
    collection: Optional[str] = None,
    credentials_path: Optional[str] = None,
    database: Optional[str] = None,
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
