from pathlib import Path
import os
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_ROOT.parent


def setup_backend_path():
    for path in (BACKEND_ROOT, REPO_ROOT):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def setup_django(settings_module='sentiment_monitor.settings'):
    setup_backend_path()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    import django

    django.setup()
