"""
LLMProxyfier — библиотека для создания прокси-сервера между клиентами
и целевыми LLM API (OpenAI, NVIDIA, Groq и др.).

Использование:
    from library import ProxyRouter

    router = ProxyRouter()

    @router.endpoint("/v1")
    def config_v1(req):
        return router.route(
            target_url="https://integrate.api.nvidia.com/v1",
            proxy="http://proxy:8080",      # необязательно
            auth_header="X-Forwarded-Token",
        )

    # Или через add_endpoint:
    router.add_endpoint(
        path="/v2",
        target_url="http://127.0.0.1:1234/v1",
        proxy="",
        auth_header="Authorization",
    )

    # Запуск:
    from library import run_server
    run_server(router, port=8080)
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urljoin
from urllib.parse import urlparse

from aiohttp import web, ClientSession, TCPConnector, ClientTimeout, ClientConnectionError

log = logging.getLogger("llmproxyfier")


# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8080
DEFAULT_HOST = "0.0.0.0"
DEFAULT_AUTH_HEADER = "X-Forwarded-Token"
DEFAULT_TIMEOUT_TOTAL = 600
DEFAULT_TIMEOUT_CONNECT = 60


# ---------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------

@dataclass
class EndpointConfig:
    """Конфигурация одного эндпоинта."""
    path: str
    target_url: str
    proxy: str = ""
    auth_header: str = DEFAULT_AUTH_HEADER
    description: str = ""


@dataclass
class EndpointRoute:
    """Скомпилированный маршрут для aiohttp."""
    prefix: str
    config_factory: Callable[[], EndpointConfig]


# ---------------------------------------------------------------------------
# Роутер
# ---------------------------------------------------------------------------

class ProxyRouter:
    """Регистрирует эндпоинты и обрабатывает проксирование."""

    def __init__(self, default_auth_header: str = DEFAULT_AUTH_HEADER) -> None:
        self._endpoints: list[EndpointRoute] = []
        self.default_auth_header = default_auth_header

    # ------------------------------------------------------------------
    # Регистрация эндпоинтов
    # ------------------------------------------------------------------

    def add_endpoint(
        self,
        path: str,
        target_url: str,
        proxy: str = "",
        auth_header: str = DEFAULT_AUTH_HEADER,
        description: str = "",
    ) -> None:
        """Добавляет один эндпоинт."""
        # strip только.trailing slash (rstrip удаляет все символы из set)
        path = path if not path.endswith("/") else path[:-1]

        def factory() -> EndpointConfig:
            return EndpointConfig(
                path=path,
                target_url=target_url,
                proxy=proxy,
                auth_header=auth_header,
                description=description,
            )

        self._endpoints.append(EndpointRoute(prefix=path, config_factory=factory))
        log.info("Registered endpoint: %s → %s %s",
                 path, target_url, f"(proxy: {proxy})" if proxy else "")

    def endpoint(self, path: str) -> Callable:
        """Декоратор для регистрации эндпоинта."""
        def decorator(func: Callable[[web.Request], EndpointConfig]) -> Callable:
            path_clean = path if not path.endswith("/") else path[:-1]

            def factory() -> EndpointConfig:
                return func  # вернём функцию, а не результат

            # Храним функцию как атрибут
            route = EndpointRoute(prefix=path_clean, config_factory=factory)
            route._config_func = func  # type: ignore[attr-defined]
            self._endpoints.append(route)
            log.info("Registered endpoint (decorator): %s", path_clean)

            async def handler(request: web.Request) -> web.StreamResponse:
                config = func(request)
                return await self._handle_proxy(request, config)

            return handler

        return decorator

    # ------------------------------------------------------------------
    # Поиск подходящего эндпоинта
    # ------------------------------------------------------------------

    def _find_endpoint(self, path: str) -> tuple[EndpointConfig | None, str]:
        """Находит endpoint для данного path и возвращает (config, remaining_path)."""
        for route in self._endpoints:
            if path.startswith(route.prefix):
                config = route.config_factory()
                remaining = path[len(route.prefix):] or "/"
                return config, remaining

        return None, path

    # ------------------------------------------------------------------
    # Проксирование
    # ------------------------------------------------------------------

    async def _handle_proxy(
        self,
        request: web.Request,
        config: EndpointConfig,
    ) -> web.StreamResponse:
        """Проксирование запроса на целевой API."""
        remaining_path = request.path[len(config.path):] or "/"
        target_url = urljoin(config.target_url.rstrip("/") + "/", remaining_path.lstrip("/"))

        # Собираем заголовки
        extra_headers = self._strip_headers(dict(request.headers))

        # Переносим API-токен
        forwarded_token = request.headers.get(config.auth_header, "")
        if forwarded_token:
            extra_headers["Authorization"] = f"Bearer {forwarded_token}"
        elif "Authorization" in request.headers:
            extra_headers["Authorization"] = request.headers["Authorization"]

        # Тело запроса
        body = await request.read()
        method = request.method
        params = dict(request.query_string.items()) if request.query_string else None

        log.info("%s  %s  →  %s  (proxy=%s, body=%d B)",
                 method, request.path, target_url, config.proxy or "none", len(body))

        # Streaming?
        want_stream = self._check_stream_wanted(request, body)

        if want_stream:
            return await self._streaming_response(request, target_url, method, body,
                                                  extra_headers, params, config.proxy)
        else:
            return await self._regular_response(request, target_url, method, body,
                                                extra_headers, params, config.proxy)

    async def _regular_response(
        self,
        request: web.Request,
        target_url: str,
        method: str,
        body: bytes,
        headers: dict[str, str],
        params: dict | None,
        proxy_url: str,
    ) -> web.Response:
        connector = TCPConnector(enable_cleanup_closed=True)
        timeout = ClientTimeout(total=DEFAULT_TIMEOUT_TOTAL, connect=DEFAULT_TIMEOUT_CONNECT)
        async with ClientSession(connector=connector, timeout=timeout,
                                  proxy=proxy_url or None) as session:
            resp = await session.request(
                method, target_url, headers=headers, params=params,
                data=body if body else None,
            )

            resp_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in {"transfer-encoding", "connection"}
            }
            resp_body = await resp.read()

            return web.Response(
                status=resp.status,
                body=resp_body,
                content_type=resp.headers.get("Content-Type", "application/json"),
                headers=resp_headers,
            )

    async def _streaming_response(
        self,
        request: web.Request,
        target_url: str,
        method: str,
        body: bytes,
        headers: dict[str, str],
        params: dict | None,
        proxy_url: str,
    ) -> web.StreamResponse:
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await response.prepare(request)

        connector = TCPConnector(limit=10, enable_cleanup_closed=True)
        # Добавляем таймаут для сокета
        timeout = ClientTimeout(
            total=DEFAULT_TIMEOUT_TOTAL,
            connect=DEFAULT_TIMEOUT_CONNECT,
            sock_read=60,  # Таймаут для чтения данных
        )

        try:
            async with ClientSession(connector=connector, timeout=timeout,
                                      proxy=proxy_url or None) as session:
                resp = await session.request(
                    method, target_url, headers=headers, params=params,
                    data=body if body else None,
                )
                try:
                    log.info("Streaming: %s %s", method, target_url)

                    # Прозрачно передаём байты от целевого API клиенту
                    try:
                        while True:
                            try:
                                chunk = await asyncio.wait_for(resp.content.readany(), timeout=60.0)
                            except asyncio.TimeoutError:
                                log.warning("Timeout reading chunk from target API")
                                break
                            if not chunk:
                                break
                            try:
                                # Добавляем таймаут для записи чанка
                                await asyncio.wait_for(response.write(chunk), timeout=10.0)
                            except asyncio.TimeoutError:
                                log.warning("Timeout writing chunk to client, closing stream")
                                break
                            except (ClientConnectionError, ConnectionResetError, OSError) as e:
                                # Клиент отключился
                                log.debug("Client disconnected during streaming: %s", e)
                                break
                    except Exception as e:
                        log.error("Error reading chunk from target API: %s", e)
                finally:
                    await resp.release()
        except (ConnectionError, TimeoutError, OSError) as exc:
            log.error("Streaming error: %s", exc)
            try:
                await response.write_eof()
            except Exception:
                pass
        except Exception as exc:
            log.error("Unexpected streaming error: %s", exc)
            try:
                await response.write_eof()
            except Exception:
                pass
        finally:
            try:
                await asyncio.wait_for(response.write_eof(), timeout=5.0)
            except asyncio.TimeoutError:
                log.warning("Timeout writing EOF to client")
            except (ClientConnectionError, ConnectionResetError, OSError):
                pass

        return response

    # ------------------------------------------------------------------
    # Хелперы
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_headers(headers: dict[str, str]) -> dict[str, str]:
        SKIP = {"host", "connection", "content-length"}
        return {k: v for k, v in headers.items() if k.lower() not in SKIP}

    @staticmethod
    def _check_stream_wanted(request: web.Request, body: bytes) -> bool:
        if "X-Stream" in request.headers:
            return request.headers["X-Stream"].lower() in ("1", "true", "yes")
        content_type = request.headers.get("Content-Type", "")
        if "application/json" in content_type and body:
            try:
                data = json.loads(body)
                if data.get("stream", False):
                    return True
            except (json.JSONDecodeError, ValueError):
                pass
        return False

    # ------------------------------------------------------------------
    # Создание приложения
    # ------------------------------------------------------------------

    def create_app(self) -> web.Application:
        """Создаёт aiohttp-приложение с зарегистрированными эндпоинтами."""
        app = web.Application()

        # Health-check
        async def health_check(request: web.Request) -> web.Response:
            endpoints_info = []
            for route in self._endpoints:
                cfg = route.config_factory()
                endpoints_info.append({
                    "path": cfg.path,
                    "target": cfg.target_url,
                    "proxy": cfg.proxy or "none",
                    "auth_header": cfg.auth_header,
                    "description": cfg.description,
                })
            return web.json_response({
                "status": "ok",
                "endpoints": endpoints_info,
            })

        app.router.add_get("/health", health_check)
        app.router.add_get("/health/", health_check)

        # Прокси-маршруты
        for route in self._endpoints:
            cfg = route.config_factory()
            proxy_resource = app.router.add_resource(cfg.path + "/{path:.*}")
            proxy_resource.add_route("GET", self._make_handler(route))
            proxy_resource.add_route("POST", self._make_handler(route))
            proxy_resource.add_route("PUT", self._make_handler(route))
            proxy_resource.add_route("PATCH", self._make_handler(route))
            proxy_resource.add_route("DELETE", self._make_handler(route))
            proxy_resource.add_route("HEAD", self._make_handler(route))
            proxy_resource.add_route("OPTIONS", self._make_handler(route))

        # CORS
        app.middlewares.append(self._cors_middleware)

        return app

    def _make_handler(self, route: EndpointRoute) -> Callable:
        async def handler(request: web.Request) -> web.StreamResponse:
            config = route.config_factory()
            return await self._handle_proxy(request, config)
        return handler

    @staticmethod
    async def _cors_middleware(app, handler):
        async def middleware(request):
            if request.method == "OPTIONS":
                return web.Response(
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": "*",
                        "Access-Control-Max-Age": "3600",
                    }
                )
            resp = await handler(request)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Headers"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            return resp
        return middleware


# ---------------------------------------------------------------------------
# Проверка прокси
# ---------------------------------------------------------------------------

def check_proxy_connection(proxy_url: str) -> bool:
    """Проверяет работоспособность прокси-сервера."""
    if not proxy_url:
        log.info("No proxy specified, using direct connections")
        return True
    
    try:
        parsed = urlparse(proxy_url)
        if not parsed.scheme or not parsed.netloc:
            log.error("Invalid proxy URL format: %s", proxy_url)
            return False
        
        # Извлекаем хост и порт
        host = parsed.hostname
        port = parsed.port or (8080 if parsed.scheme == "http" else 443)
        
        # Проверяем подключение
        log.info("Checking proxy connection to %s:%s...", host, port)
        
        # Создаем сокет для проверки подключения
        with socket.create_connection((host, port), timeout=5):
            log.info("Proxy connection successful: %s", proxy_url)
            return True
            
    except socket.timeout:
        log.error("Proxy connection timeout: %s", proxy_url)
        return False
    except socket.gaierror:
        log.error("Proxy host not found: %s", proxy_url)
        return False
    except ConnectionRefusedError:
        log.error("Proxy connection refused: %s", proxy_url)
        return False
    except Exception as e:
        log.error("Proxy connection error: %s - %s", proxy_url, str(e))
        return False


# ---------------------------------------------------------------------------
# Утилита запуска
# ---------------------------------------------------------------------------

def run_server(router: ProxyRouter, port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, proxy: str = None) -> None:
    """Запускает прокси-сервер."""
    # Проверяем прокси перед запуском
    if proxy:
        log.info("Proxy specified via CLI: %s", proxy)
        if not check_proxy_connection(proxy):
            log.error("Failed to connect to proxy server. Server will not start.")
            return
    else:
        # Проверяем, есть ли прокси в эндпоинтах по умолчанию
        default_proxies = set(route.config_factory().proxy for route in router._endpoints if route.config_factory().proxy)
        if default_proxies:
            log.info("Using default proxy settings from endpoints configuration")
            # Проверяем все уникальные прокси по умолчанию
            for default_proxy in default_proxies:
                if not check_proxy_connection(default_proxy):
                    log.warning("Default proxy %s is not reachable, but server will start anyway", default_proxy)
        else:
            log.info("No proxy specified, using direct connections")
    
    # Если передан глобальный прокси через CLI, обновляем конфигурацию эндпоинтов
    if proxy:
        for route in router._endpoints:
            cfg = route.config_factory()
            if hasattr(route, '_config_func'):
                # Для декораторов нужно обновить функцию
                original_func = route._config_func
                def make_factory(original_cfg):
                    def factory():
                        new_cfg = original_cfg()
                        new_cfg.proxy = proxy
                        return new_cfg
                    return factory
                route.config_factory = make_factory(original_func)
            else:
                # Для add_endpoint обновляем напрямую
                def make_factory(original_factory):
                    def factory():
                        new_cfg = original_factory()
                        new_cfg.proxy = proxy
                        return new_cfg
                    return factory
                route.config_factory = make_factory(route.config_factory)

    app = router.create_app()

    log.info("=" * 60)
    log.info("  LLMProxyfier")
    log.info("=" * 60)
    log.info("  Listen : %s:%d", host, port)
    if proxy:
        log.info("  Global Proxy : %s", proxy)
    log.info("  Endpoints:")
    for route in router._endpoints:
        cfg = route.config_factory()
        proxy_str = f" (proxy: {cfg.proxy})" if cfg.proxy else ""
        log.info("    %s → %s%s", cfg.path, cfg.target_url, proxy_str)
    log.info("=" * 60)

    web.run_app(app, host=host, port=port)
