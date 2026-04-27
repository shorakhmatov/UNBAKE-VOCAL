@echo off
echo ==========================================
echo Unbake Vocal Recognition - Test Runner
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+
    exit /b 1
)

REM Check virtual environment
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate

REM Install dependencies
echo.
echo Installing dependencies...
pip install -q -r requirements.txt

REM Create directories
echo.
echo Setting up directories...
mkdir data test_data results 2>nul

REM Run comparison test
echo.
echo ==========================================
echo Running Model Comparison
echo ==========================================
python src/evaluate.py --compare

REM Check results
echo.
echo ==========================================
echo Test Results
echo ==========================================
if exist results\comparison_results.json (
    echo ✓ Results saved to results\comparison_results.json
    type results\evaluation_report.md 2>nul
) else (
    echo ⚠ No results generated. Check errors above.
)

echo.
echo ==========================================
echo Tests Complete
echo ==========================================
pause
