@echo off
set ENVBIN=..\..\env\Scripts
@rem should kill agent if already running --- kill $(lsof -t -i :8000)

@rem This is the cli entry point for the benchmarking tool.
@rem To run this in server mode pass in `serve` as the first argument.
%ENVBIN%\poetry run agbenchmark %*
