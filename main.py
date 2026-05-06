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
from library import run_server

# ---------------------------------------------------------------------------
# Логирование
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='LLMProxyfier - Proxy server for LLM APIs')
    parser.add_argument('--port', '-p', type=int, default=8080,
                       help='Port to run the server on (default: 8080)')
    parser.add_argument('--host', type=str, default="0.0.0.0",
                       help='Host to bind the server to (default: 0.0.0.0)')
    
    args = parser.parse_args()
    
    router = create_router()
    run_server(router, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
