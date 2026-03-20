"""Root conftest for test configuration."""

import importlib

# Skip collection of test files that import unavailable modules.
# These are integration tests referencing a removed module (lex.core.clients)
# and will fail at import time regardless of markers.
collect_ignore_glob = []

_OPTIONAL_MODULES = ["lex.core.clients"]
for mod in _OPTIONAL_MODULES:
    try:
        importlib.import_module(mod)
    except ModuleNotFoundError:
        collect_ignore_glob.extend(
            [
                "lex/core/test_document_integration.py",
                "lex/core/test_utils_integration.py",
                "lex/test_pipeline_integration.py",
            ]
        )
        break
