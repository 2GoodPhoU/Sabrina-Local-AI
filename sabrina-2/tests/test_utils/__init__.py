"""Test scaffolding utilities for the Sabrina rebuild.

`paths`  — project/test directory helpers and the sys.path bootstrap.
`mocks`  — protocol-typed fakes for Brain / Listener / Speaker / EventBus
           and a small CancelToken factory. New code, not a port — the
           legacy mocks targeted abstractions the rebuild rejected.
"""
