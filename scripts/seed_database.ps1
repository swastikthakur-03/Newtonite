# Seed initial users, teams, and work items
$env:PYTHONPATH = "backend"
& "backend/venv/Scripts/python.exe" backend/app/seed.py
