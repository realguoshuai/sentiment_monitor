# Backend Scripts

This folder collects ad-hoc, diagnostic, migration, verification, and one-off test scripts that are not part of the runtime application.

- `sitecustomize.py` injects the repo root and `backend/` into `sys.path`, so Django-related scripts can still be run directly from this folder.
- Runtime entrypoints remain where they belong, such as `backend/manage.py`.
- Product code should stay under `backend/api/`, `backend/collector/`, and the Django project package, not here.
