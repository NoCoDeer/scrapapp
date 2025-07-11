#!/usr/bin/env python3
"""
Главный файл управления системой скрапинга.
"""
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent))

from scraper.management.cli import cli

if __name__ == '__main__':
    cli()
