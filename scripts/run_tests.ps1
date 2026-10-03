# Script to run pytest test suite on PostgreSQL test database
$env:PYTHONPATH = "backend"
& "backend/venv/Scripts/pytest.exe" -v backend/tests
