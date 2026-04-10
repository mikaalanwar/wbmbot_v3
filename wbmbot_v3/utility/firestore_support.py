import importlib
import importlib.abc
import importlib.machinery
import os
import sys
from typing import Any

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

    if not any(getattr(finder, "_wbm_blocker", False) for finder in sys.meta_path):

        class _BlockUpbLoader(importlib.abc.Loader):
            def create_module(self, spec: object) -> None:
                return None

            def exec_module(self, module: object) -> None:
                raise ImportError(str(module))

        class _BlockUpbFinder(importlib.abc.MetaPathFinder):
            _wbm_blocker = True

            def find_spec(self, fullname: str, path: object, target: object = None):
                if fullname.startswith(blocked_prefixes):
                    return importlib.machinery.ModuleSpec(
                        fullname,
                        _BlockUpbLoader(),
                    )
                return None

        sys.meta_path.insert(0, _BlockUpbFinder())


def configure_credentials(credentials_path: str | None) -> None:
    if credentials_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path


def get_firestore_dependencies() -> tuple[Any, type[Exception]]:
    global _FIRESTORE, _GOOGLE_API_ERROR
    if _FIRESTORE is None or _GOOGLE_API_ERROR is None:
        from google.api_core.exceptions import GoogleAPIError
        from google.cloud import firestore

        _FIRESTORE = firestore
        _GOOGLE_API_ERROR = GoogleAPIError
    return _FIRESTORE, _GOOGLE_API_ERROR


def create_firestore_client(
    project_id: str | None = None,
    database: str | None = None,
    credentials_path: str | None = None,
) -> tuple[Any, type[Exception]]:
    configure_credentials(credentials_path)
    _patch_protobuf_imports_for_py314()
    firestore, google_api_error = get_firestore_dependencies()
    if database:
        return (
            firestore.Client(project=project_id, database=database),
            google_api_error,
        )
    return firestore.Client(project=project_id), google_api_error
