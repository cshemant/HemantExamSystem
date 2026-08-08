#!/bin/sh
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
python3 app.py
