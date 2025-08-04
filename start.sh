#!/bin/bash
echo "🚀 Installing Playwright Browsers..."
playwright install

echo "▶️  Starting Agent Bot..."
python3 main.py
