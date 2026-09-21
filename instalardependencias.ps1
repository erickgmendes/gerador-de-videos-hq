# Prepara o ambiente do projeto: cria o venv, instala dependencias e aplica migrations.
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual (.venv)..."
    py -3.12 -m venv .venv
} else {
    Write-Host "Ambiente virtual (.venv) ja existe, pulando criacao."
}

Write-Host "Instalando dependencias do projeto..."
.\.venv\Scripts\python.exe -m pip install -e .

Write-Host "Aplicando migrations do banco de dados..."
.\.venv\Scripts\python.exe -m alembic upgrade head

Write-Host "Ambiente pronto! Use .\start.ps1 para iniciar o servidor."
