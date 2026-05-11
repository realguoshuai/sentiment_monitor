import os

import uvicorn


def main() -> None:
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
