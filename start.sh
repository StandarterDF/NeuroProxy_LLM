# LLMProxyfier Start Script for Unix/Linux/macOS
# Usage: ./start.sh [port] [host] [proxy]
# Example: ./start.sh 8080 0.0.0.0 http://proxy.example.com:8080

# Set default values
PORT=${1:-8080}
HOST=${2:-0.0.0.0}
PROXY=${3:-}

# Display configuration
echo "Starting LLMProxyfier..."
echo "Port: $PORT"
echo "Host: $HOST"
if [ -n "$PROXY" ]; then
    echo "Proxy: $PROXY"
else
    echo "Proxy: None (using defaults)"
fi
echo ""

# Check if Python is available
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "Error: Python is not installed"
    exit 1
fi

# Determine which Python command to use
PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
    PYTHON_CMD="python3"
fi

# Build the command
CMD="$PYTHON_CMD main.py --port $PORT --host $HOST"
if [ -n "$PROXY" ]; then
    CMD="$CMD --proxy $PROXY"
fi

# Run the server
eval $CMD