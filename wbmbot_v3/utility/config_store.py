import json
import os
from typing import Optional

from helpers import constants
from logger import wbm_logger
from utility import io_operations
from utility.application_store import _patch_protobuf_imports_for_py314

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
color_me = wbm_logger.ColoredLogger(__appname__)
LOG = color_me.create_logger()

_FIRESTORE = None
_GOOGLE_API_ERROR = None


class ConfigStore:
    def initialize(self) -> None:
        return None

    def load_config(self, config_key: Optional[str] = None):
        raise NotImplementedError

    def list_configs(self):
        raise NotImplementedError

    def save_config(self, config_key: str, config: dict) -> None:
        raise NotImplementedError


class FileConfigStore(ConfigStore):
    def __init__(self, path: str, allow_prompt: bool = True):
        self.path = path
        self.allow_prompt = allow_prompt

    def load_config(self, config_key: Optional[str] = None):
        if self.allow_prompt:
            return io_operations.load_wbm_config(self.path)
        return io_operations.load_wbm_config_no_prompt(self.path)

    def list_configs(self):
        config = self.load_config()
        return [config] if config else []

    def save_config(self, config_key: str, config: dict) -> None:
        io_operations.create_directory_if_not_exists(os.path.dirname(self.path))
        with open(self.path, "w", encoding="utf-8") as outfile:
            json.dump(config, outfile, indent=4, ensure_ascii=False)


class FirestoreConfigStore(ConfigStore):
    def __init__(
        self,
        project_id: Optional[str] = None,
        collection: Optional[str] = None,
        credentials_path: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.project_id = project_id
        self.collection_name = collection or "wbm_users"
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
                "Using Firestore config store "
                f"(project={self._client.project}, "
                f"collection={self.collection_name}) 🧾"
            )
        )

    def load_config(self, config_key: Optional[str] = None):
        if not self._collection:
            raise RuntimeError("Firestore config store not initialized.")
        if not config_key:
            raise ValueError("config_key is required for Firestore config store.")
        try:
            doc = self._collection.document(config_key).get()
        except _GOOGLE_API_ERROR as exc:
            LOG.error(color_me.red(f"Firestore read failed: {exc}"))
            raise
        if not doc.exists:
            raise FileNotFoundError(
                f"No config found in Firestore for key '{config_key}'."
            )
        data = doc.to_dict() or {}
        data.pop("_id", None)
        data.setdefault("user_id", doc.id)
        return data

    def list_configs(self):
        if not self._collection:
            raise RuntimeError("Firestore config store not initialized.")
        try:
            docs = list(self._collection.stream())
        except _GOOGLE_API_ERROR as exc:
            LOG.error(color_me.red(f"Firestore read failed: {exc}"))
            raise
        configs = []
        for doc in docs:
            data = doc.to_dict() or {}
            data.pop("_id", None)
            data.setdefault("user_id", doc.id)
            configs.append(data)
        return configs

    def save_config(self, config_key: str, config: dict) -> None:
        if not self._collection:
            raise RuntimeError("Firestore config store not initialized.")
        if not config_key:
            raise ValueError("config_key is required for Firestore config store.")
        payload = dict(config)
        payload["user_id"] = config_key
        try:
            self._collection.document(config_key).set(payload, merge=True)
            LOG.info(
                color_me.green(
                    f"Saved WBM config in Firestore (key={config_key}) ✅"
                )
            )
        except _GOOGLE_API_ERROR as exc:
            LOG.error(color_me.red(f"Firestore write failed: {exc}"))
            raise


def build_config_store(
    backend: str,
    path: str,
    allow_prompt: bool = True,
    project_id: Optional[str] = None,
    collection: Optional[str] = None,
    credentials_path: Optional[str] = None,
    database: Optional[str] = None,
) -> ConfigStore:
    backend = (backend or "file").strip().lower()
    if backend == "firestore":
        return FirestoreConfigStore(
            project_id=project_id,
            collection=collection,
            credentials_path=credentials_path,
            database=database,
        )
    return FileConfigStore(path, allow_prompt=allow_prompt)
