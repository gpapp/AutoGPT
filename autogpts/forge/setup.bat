@echo off

set ENVBIN=..\..\env\Scripts

@rem ENV_PATH=`%ENVBIN%\poetry env info --path`
 

 %ENVBIN%\poetry install --extras benchmark
 echo "Setup completed successfully."
 exit 0
