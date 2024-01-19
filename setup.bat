@echo off

python -c "print('Python Found')"
if %errorlevel% neq 0 echo Cannot find python && exit /b %errorlevel%
if not exist .\env (
	python -m venv env
	env\Scripts\python -m pip install --upgrade pip
)
env\Scripts\pip install poetry
	