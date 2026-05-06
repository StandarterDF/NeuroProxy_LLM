# LLMProxyfier

Прокси-сервер для LLM API, позволяющий маршрутизировать запросы к различным провайдерам LLM (Mistral, NVIDIA, OpenRouter и др.) через единую локальную точку входа.

## Установка

### Требования
- Python 3.7+
- Установленные зависимости: `aiohttp`

### Установка зависимостей
```bash
pip install aiohttp
```

## Использование

### Запуск сервера
```bash
python main.py [PORT]
```

Где `[PORT]` - опциональный параметр порта (по умолчанию: 8080).

Пример:
```bash
python main.py 8081
```

### Настройка эндпоинтов
Эндпоинты настраиваются в файле `endpoints.py`. По умолчанию доступны следующие маршруты:

- `/v1` → Mistral API (`https://api.mistral.ai/v1`)
- `/v2` → NVIDIA NIM API (`https://integrate.api.nvidia.com/v1`)
- `/v3` → OpenRouter API (`https://openrouter.ai/api/v1`)
- `/v0` → Локальный API (`http://127.0.0.1:1234/v1`)

### Примеры использования в клиентских приложениях

#### Open WebUI, Chatbot UI и др.
Укажите следующие параметры:
- **Base URL**: `http://localhost:8080/v1` (для Mistral)
- **Base URL**: `http://localhost:8080/v2` (для NVIDIA)
- **Base URL**: `http://localhost:8080/v3` (для OpenRouter)
- **Base URL**: `http://localhost:8080/v0` (для локального API)

#### API Key
API ключ передается через заголовок `X-Forwarded-Token`. Пример:
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "X-Forwarded-Token: ваш-api-ключ" \
  -H "Content-Type: application/json" \
  -d '{"model": "mistral-tiny", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Проверка состояния сервера
```bash
curl http://localhost:8080/health
```

Ответ будет содержать информацию о всех зарегистрированных эндпоинтах.

## Настройка

### Добавление новых эндпоинтов
Для добавления нового эндпоинта отредактируйте файл `endpoints.py`:

```python
router.add_endpoint(
    path="/v4",
    target_url="https://api.example.com/v1",
    proxy="http://proxy.example.com:8080",  # опционально
    auth_header="X-Forwarded-Token",
    description="Example API",
)
```

### Параметры эндпоинта
- `path`: Локальный путь (например, `/v1`)
- `target_url`: Целевой URL API
- `proxy`: URL прокси-сервера (опционально)
- `auth_header`: Заголовок для передачи API ключа (по умолчанию: `X-Forwarded-Token`)
- `description`: Описание эндпоинта

## CLI

Для удобного запуска сервера вы можете использовать CLI:

```bash
python -m main [PORT]
```

Пример:
```bash
python -m main 8081
```

## Логирование
Сервер логирует все запросы в стандартный вывод. Формат лога:
```
YYYY-MM-DD HH:MM:SS  LEVEL      MESSAGE
```

## Лицензия
MIT