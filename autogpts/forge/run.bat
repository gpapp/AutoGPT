@echo off
@rem should kill agent if already running --- kill $(lsof -t -i :8000)

set ENVBIN=..\..\env\Scripts

if not exist .env (
	copy .env.example .env
  echo "Please add your api keys to the .env file."
)
%ENVBIN%\poetry run python -m forge
