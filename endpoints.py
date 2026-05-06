"""
Конфигурация эндпоинтов LLMProxyfier.

Примеры использования в программах (Open WebUI, Chatbot UI и др.):
    Base URL: http://localhost:8080/v1     — для Mistral
    Base URL: http://localhost:8080/v2     — для NVIDIA
    Base URL: http://localhost:8080/v3     — для OpenRouter
    Base URL: http://localhost:8080/ollama — для локального API
"""

from library import ProxyRouter

HTTP_PROXY = "http://127.0.0.1:2081"

def create_router() -> ProxyRouter:
    """Создаёт и настраивает роутер."""
    router = ProxyRouter(default_auth_header="X-Forwarded-Token")

    # --- Mistral API ---
    router.add_endpoint(
        path="/v1",
        target_url="https://api.mistral.ai/v1",
        proxy=HTTP_PROXY,  # например: "http://proxy.example.com:8080"
        auth_header="X-Forwarded-Token",
        description="Mistral API",
    )

    # --- NVIDIA NIM API ---
    router.add_endpoint(
        path="/v2",
        target_url="https://integrate.api.nvidia.com/v1",
        proxy=HTTP_PROXY,  # например: "http://proxy.example.com:8080"
        auth_header="X-Forwarded-Token",
        description="NVIDIA NIM API",
    )

    # --- OpenRouter API ---
    router.add_endpoint(
        path="/v3",
        target_url="https://openrouter.ai/api/v1",
        proxy=HTTP_PROXY,  # например: "http://proxy.example.com:8080"
        auth_header="X-Forwarded-Token",
        description="OpenRouter API",
    )

    # --- Локальный API (LM Studio / llama.cpp / Ollama) ---
    router.add_endpoint(
        path="/v0",
        target_url="http://127.0.0.1:1234/v1",
        proxy="",  # например: "http://proxy.example.com:8080"
        auth_header="",
        description="Local API (127.0.0.1:1234)",
    )

    return router
