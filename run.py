#!/usr/bin/env python3
"""
SlopLens — One command startup
Run: python run.py
Then open: http://localhost:8000
"""
import subprocess, sys, os, pathlib

root    = pathlib.Path(__file__).parent
backend = root / "backend"

print("\n🔍 SlopLens v4.0.0")
print("─" * 50)

env_file = root / ".env"
if not env_file.exists():
    import shutil
    shutil.copy(root / ".env.example", env_file)
    print("⚠  .env created — add GROQ_API_KEY")
    print("   Get free key: https://console.groq.com\n")

print("Starting backend + frontend...")
print()
print("  Home:      http://localhost:8000")
print("  Analyzer:  http://localhost:8000/pages/analyzer.html")
print("  Compare:   http://localhost:8000/pages/compare.html")
print("  Repo:      http://localhost:8000/pages/repo.html")
print("  URLs:      http://localhost:8000/pages/urls.html")
print("  Badge:     http://localhost:8000/pages/badge.html")
print("  Extension: http://localhost:8000/pages/extension.html")
print("  CLI Guide: http://localhost:8000/pages/cli.html")
print("  API Docs:  http://localhost:8000/docs")
print("  API Guide: http://localhost:8000/pages/api.html")
print()
print("Press Ctrl+C to stop")
print("─" * 50)

os.chdir(backend)
subprocess.run([
    sys.executable, "-m", "uvicorn", "main:app",
    "--reload", "--port", "8000", "--host", "0.0.0.0"
])