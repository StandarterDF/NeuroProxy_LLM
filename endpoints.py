"""
Конфигурация эндпоинтов LLMProxyfier.

Примеры использования в программах (Open WebUI, Chatbot UI и др.):
    Base URL: http://localhost:8080/v1     — для Mistral
    Base URL: http://localhost:8080/v2     — для NVIDIA
    Base URL: http://localhost:8080/v3     — для OpenRouter
    Base URL: http://localhost:8080/ollama — для локального API

Примеры использования кастомных обработчиков:
    # В коде:
    router.set_custom_handler("/v3/models", my_handler, enabled=True)

    # В CLI:
    python -m LLMProxyfier --no-custom-handlers  # отключить все обработчики
"""

import asyncio
import json
import logging
from typing import Any

from aiohttp import web

from library import ProxyRouter, EndpointConfig

log = logging.getLogger("llmproxyfier")

HTTP_PROXY = "http://127.0.0.1:2081"
SOCKS_PROXY = "socks5://127.0.0.1:2080"


# ---------------------------------------------------------------------------
# Примеры кастомных обработчиков
# ---------------------------------------------------------------------------

async def handler_filter_free_models(
    request: web.Request,
    config: EndpointConfig,
    target_url: str,
    method: str,
    body: bytes,
    headers: dict[str, str],
    params: dict | None,
) -> web.Response | None:
    """
    Кастомный обработчик: для /v3/models возвращает только бесплатные модели.
    Для всех остальных путей возвращает None → запрос идёт дальше как обычный прокси.
    """
    # Работаем только с /v3/models
    if request.path != "/v3/models" and not request.path.startswith("/v3/models"):
        return None  # ← пробросить дальше как обычный прокси

    log.info("handler_filter_free_models: запрашиваю модели из OpenRouter API...")

    # Делаем запрос к реальному API
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://openrouter.ai/api/v1/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    log.error("handler_filter_free_models: API вернул %d", resp.status)
                    body_raw = await resp.read()
                    return web.Response(
                        status=resp.status,
                        body=body_raw,
                        content_type="application/json",
                    )

                data = await resp.json()
                models = data.get("data", [])

                # Фильтруем бесплатные модели (prompt == 0 AND completion == 0)
                free_models = []
                for m in models:
                    pricing = m.get("pricing", {})
                    prompt_cost = float(pricing.get("prompt", "1"))
                    completion_cost = float(pricing.get("completion", "1"))
                    if prompt_cost == 0.0 and completion_cost == 0.0:
                        free_models.append({
                            "id": m["id"],
                            "name": m.get("name"),
                            "context": m.get("context_length"),
                        })

                log.info("handler_filter_free_models: найдено %d бесплатных моделей из %d",
                         len(free_models), len(models))

                # Возвращаем формат, совместимый с оригинальным API (/v3/models)
                return web.json_response({
                    "data": free_models,
                })

    except asyncio.TimeoutError:
        log.error("handler_filter_free_models: таймаут запроса к OpenRouter")
        return web.json_response(
            {"error": {"message": "Timeout fetching models from OpenRouter", "type": "timeout"}},
            status=504,
        )
    except Exception as e:
        log.error("handler_filter_free_models: ошибка — %s", e)
        return web.json_response(
            {"error": {"message": str(e), "type": "internal"}},
            status=500,
        )


async def handler_passthrough(
    request: web.Request,
    config: EndpointConfig,
    target_url: str,
    method: str,
    body: bytes,
    headers: dict[str, str],
    params: dict | None,
) -> web.Response:
    """
    Простой обработчик-заглушка: просто пробрасывает запрос дальше.
    Используйте это как шаблон для своих обработчиков.
    """
    log.info("handler_passthrough: %s %s", method, request.path)
    # В реальном коде вы можете модифицировать body, headers и т.д.
    # Здесь просто возвращаем "OK" для демонстрации
    return web.json_response({"status": "ok", "path": request.path})


# ---------------------------------------------------------------------------
# Создание роутера
# ---------------------------------------------------------------------------

def create_router(proxy_override: str = None) -> ProxyRouter:
    """Создаёт и настраивает роутер."""
    router = ProxyRouter(default_auth_header="X-Forwarded-Token")

    # Используем переданный прокси или значение по умолчанию
    effective_proxy = proxy_override if proxy_override is not None else HTTP_PROXY

    # --- Mistral API ---
    router.add_endpoint(
        path="/v1",
        target_url="https://api.mistral.ai/v1",
        proxy=HTTP_PROXY,
        auth_header="X-Forwarded-Token",
        description="Mistral API",
    )

    # --- NVIDIA NIM API ---
    router.add_endpoint(
        path="/v2",
        target_url="https://integrate.api.nvidia.com/v1",
        proxy=HTTP_PROXY,
        auth_header="X-Forwarded-Token",
        description="NVIDIA NIM API",
    )

    # --- OpenRouter API ---
    # Кастомный обработчик для /v3/models — только бесплатные модели
    router.add_endpoint(
        path="/v3",
        target_url="https://openrouter.ai/api/v1",
        proxy=HTTP_PROXY,
        auth_header="X-Forwarded-Token",
        description="OpenRouter API",
        custom_handler=handler_filter_free_models,
        use_custom_handler=False,  # По умолчанию ВЫКЛ — включите через set_custom_handler
    )

    # --- Локальный API (LM Studio / llama.cpp / Ollama) ---
    router.add_endpoint(
        path="/v0",
        target_url="http://127.0.0.1:1234/v1",
        proxy="",  # Локальный API не использует прокси
        auth_header="",
        description="Local API (127.0.0.1:1234)",
    )

    return router


# ---------------------------------------------------------------------------
# Утилита: включение кастомных обработчиков
# ---------------------------------------------------------------------------

def enable_custom_handlers(router: ProxyRouter) -> None:
    """Включает кастомные обработчики для всех эндпоинтов.

    Вызывайте после create_router(), если хотите активировать обработчики.
    """
    # Включаем фильтр бесплатных моделей для OpenRouter
    router.set_custom_handler("/v3", handler_filter_free_models, enabled=True)
    log.info("Custom handlers enabled for all endpoints")
