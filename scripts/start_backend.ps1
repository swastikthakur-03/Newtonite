# Start the FastAPI backend server on port 8000
$env:PYTHONPATH = "backend"
& "backend/venv/Scripts/uvicorn.exe" app.main:app --app-dir backend --reload --port 8000
