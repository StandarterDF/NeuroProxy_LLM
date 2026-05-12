"""
LLMProxyfier — сервер прокси для LLM API.

Запускает прокси-сервер с эндпоинтами из endpoints.py.
Каждый эндпоинт маппит локальный путь на целевой API.

Примеры использования:
    http://localhost:8080/v1/chat/completions  →  NVIDIA
    http://localhost:8080/v2/chat/completions  →  Groq
    http://localhost:8080/v3/chat/completions  →  OpenRouter

В программах указывайте:
    Base URL: http://localhost:8080/v1
    API Key:  ваш-ключ (через заголовок X-Forwarded-Token)
"""

import logging
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импорта endpoints
sys.path.insert(0, str(Path(__file__).parent))

from endpoints import create_router
from library import run_server, check_proxy_connection

# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("llmproxyfier.main")

# Уменьшаем уровень логирования для aiohttp, чтобы уменьшить шум
logging.getLogger("aiohttp").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def handle_asyncio_exception(loop, context):
    """Глобальный обработчик исключений для asyncio."""
    if "exception" in context and isinstance(context["exception"], ConnectionResetError):
        log.warning("ConnectionResetError caught in asyncio loop: %s", context["exception"])
    else:
        log.error("Unexpected error in asyncio loop: %s", context.get("message", "Unknown error"))


def main():
    import argparse

    parser = argparse.ArgumentParser(description='LLMProxyfier - Proxy server for LLM APIs')
    parser.add_argument('--port', '-p', type=int, default=8080,
                       help='Port to run the server on (default: 8080)')
    parser.add_argument('--host', type=str, default="0.0.0.0",
                       help='Host to bind the server to (default: 0.0.0.0)')
    parser.add_argument('--proxy', type=str, default=None,
                       help='HTTP proxy to use for API connections (e.g., http://proxy.example.com:8080)')
    parser.add_argument('--no-custom-handlers',
                       action='store_true',
                       help='Disable all custom handlers globally (use raw API responses)')

    args = parser.parse_args()

    # Устанавливаем глобальный обработчик исключений для asyncio
    import asyncio
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_asyncio_exception)

    router = create_router(proxy_override=args.proxy)

    # Включаем кастомные обработчики (если не отключены через CLI)
    if not args.no_custom_handlers:
        from endpoints import enable_custom_handlers
        enable_custom_handlers(router)
    else:
        for route in router._endpoints:
            route.use_custom_handler_override = False
        log.warning("Global custom handlers DISABLED (--no-custom-handlers)")

    run_server(router, port=args.port, host=args.host, proxy=args.proxy)

    # Если сервер не запустился из-за ошибки прокси, возвращаем код ошибки
    if args.proxy:
        import time
        time.sleep(1)  # Даем время на вывод логов


if __name__ == "__main__":
    main()
