$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3.12 -m venv .venv
& "$PSScriptRoot\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$PSScriptRoot\.venv\Scripts\python.exe" -m pip install -e ".[ui,test]"
& "$PSScriptRoot\.venv\Scripts\python.exe" -m pytest -q
