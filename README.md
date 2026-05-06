# LLMProxyfier

Прокси-сервер для LLM API, позволяющий маршрутизировать запросы к различным провайдерам LLM (Mistral, NVIDIA, OpenRouter и др.) через единую локальную точку входа.

## Установка

### Требования
- Python 3.7 или выше
- pip (менеджер пакетов Python)

### Установка зависимостей

#### Вариант 1: Установка через requirements.txt (рекомендуется)

```bash
# Клонируйте репозиторий (если еще не сделали этого)
git clone https://github.com/StandarterDF/NeuroProxy_LLM
cd NeuroProxy_LLM

# Установите зависимости
pip install -r requirements.txt
```

#### Вариант 2: Ручная установка

```bash
pip install aiohttp==3.9.3
```

#### Для Windows (если возникают проблемы с установкой)

```bash
python -m pip install --upgrade pip
python -m pip install aiohttp==3.9.3
```

### Проверка установки

После установки вы можете проверить, что все работает:

```bash
python -c "import aiohttp; print('aiohttp version:', aiohttp.__version__)"
```

Должна вывестись версия aiohttp (3.9.3 или выше).

## Использование

### Запуск сервера
```bash
python main.py [--port PORT] [--host HOST] [--proxy PROXY]
```

Параметры:
- `--port`, `-p`: Порт для запуска сервера (по умолчанию: 8080)
- `--host`: Интерфейс для привязки сервера (по умолчанию: 0.0.0.0)
- `--proxy`: HTTP прокси для подключения к API (например, http://proxy.example.com:8080)

**Проверка прокси:** При запуске сервер автоматически проверяет работоспособность указанного прокси. Если прокси недоступен, сервер не запустится и вернет код ошибки 1.

Примеры:
```bash
# Запуск на порту 8081
python main.py --port 8081

# Запуск на конкретном интерфейсе
python main.py --host 127.0.0.1

# Запуск с использованием HTTP прокси
python main.py --proxy http://proxy.example.com:8080

# Комбинированный запуск
python main.py --port 8081 --host 127.0.0.1 --proxy http://proxy.example.com:8080

# Пример с неверным прокси (сервер не запустится)
python main.py --proxy http://invalid.proxy:9999
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

## Быстрый запуск

Для удобного запуска сервера доступны скрипты:

### Windows (start.bat)
```bash
start.bat [port] [host] [proxy]
```

Пример:
```bash
start.bat 8080 0.0.0.0 http://proxy.example.com:8080
```

### Unix/Linux/macOS (start.sh)
```bash
./start.sh [port] [host] [proxy]
```

Пример:
```bash
./start.sh 8080 0.0.0.0 http://proxy.example.com:8080
```

## CLI

Для запуска сервера напрямую используйте:

```bash
python main.py --help
```

Это покажет все доступные параметры командной строки.

## Логирование
Сервер логирует все запросы в стандартный вывод. Формат лога:
```
YYYY-MM-DD HH:MM:SS  LEVEL      MESSAGE
```

## Лицензия
MIT