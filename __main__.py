"""
CLI entry point for LLMProxyfier.

Allows running the proxy server via:
    python -m LLMProxyfier [PORT]
"""

import sys
from main import main

if __name__ == "__main__":
    main()