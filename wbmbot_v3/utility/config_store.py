import json
import os
from abc import ABC, abstractmethod
from typing import Any

from wbmbot_v3.logger import wbm_logger
from wbmbot_v3.utility import firestore_support, io_operations

__appname__ = os.path.splitext(os.path.basename(__file__))[0]
color_me = wbm_logger.ColoredLogger(__appname__)
LOG = color_me.create_logger()


class ConfigStore(ABC):
    def initialize(self) -> None:
        return None

    @abstractmethod
    def load_config(self, config_key: str | None = None):
        raise NotImplementedError

    @abstractmethod
    def list_configs(self):
        raise NotImplementedError

    @abstractmethod
    def save_config(self, config_key: str, config: dict) -> None:
        raise NotImplementedError


class FileConfigStore(ConfigStore):
    def __init__(self, path: str, allow_prompt: bool = True):
        self.path = path
        self.allow_prompt = allow_prompt

    def load_config(self, config_key: str | None = None):
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
        project_id: str | None = None,
        collection: str | None = None,
        credentials_path: str | None = None,
        database: str | None = None,
    ):
        self.project_id = project_id
        self.collection_name = collection or "wbm_users"
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
                "Using Firestore config store "
                f"(project={self._client.project}, "
                f"collection={self.collection_name}) 🧾"
            )
        )

    def _require_collection(self):
        if not self._collection:
            raise RuntimeError("Firestore config store not initialized.")
        return self._collection

    def _require_google_api_error(self) -> type[Exception]:
        if self._google_api_error is None:
            raise RuntimeError("Firestore config store not initialized.")
        return self._google_api_error

    def load_config(self, config_key: str | None = None):
        collection = self._require_collection()
        google_api_error = self._require_google_api_error()
        if not config_key:
            raise ValueError("config_key is required for Firestore config store.")
        try:
            doc = collection.document(config_key).get()
        except google_api_error as exc:
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
        collection = self._require_collection()
        google_api_error = self._require_google_api_error()
        try:
            docs = list(collection.stream())
        except google_api_error as exc:
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
        collection = self._require_collection()
        google_api_error = self._require_google_api_error()
        if not config_key:
            raise ValueError("config_key is required for Firestore config store.")
        payload = dict(config)
        payload["user_id"] = config_key
        try:
            collection.document(config_key).set(payload, merge=True)
            LOG.info(
                color_me.green(
                    f"Saved WBM config in Firestore (key={config_key}) ✅"
                )
            )
        except google_api_error as exc:
            LOG.error(color_me.red(f"Firestore write failed: {exc}"))
            raise


def build_config_store(
    backend: str,
    path: str,
    allow_prompt: bool = True,
    project_id: str | None = None,
    collection: str | None = None,
    credentials_path: str | None = None,
    database: str | None = None,
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
