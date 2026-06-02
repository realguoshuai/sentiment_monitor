import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    # 打包环境下，从 exe 同级目录查找 .env
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).resolve().parent

    env_file = app_dir / '.env'
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            pass

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
    port = int(os.environ.get('SENTIMENT_MONITOR_BACKEND_PORT', '8000'))
    from sentiment_monitor.asgi import application

    uvicorn.run(
        application,
        host='127.0.0.1',
        port=port,
        log_level='info',
    )


if __name__ == '__main__':
    main()
