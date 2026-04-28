import os

import uvicorn


def main() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentiment_monitor.settings')
    from sentiment_monitor.asgi import application

    uvicorn.run(
        application,
        host='127.0.0.1',
        port=8000,
        log_level='info',
    )


if __name__ == '__main__':
    main()
