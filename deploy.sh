#!/bin/bash

echo "--- Fetching parameters from AWS ---"
export $(aws ssm get-parameters-by-path \
    --path "/" \
    --recursive \
    --with-decryption \
    --region us-east-1 \
    --query "Parameters[*].[Name,Value]" \
    --output text | awk -F'/' '{print $NF}' | sed 's/\t/=/')

echo "--- Building images ---"
docker compose build

echo "--- Running Migrations ---"
docker compose up migrations --exit-code-from migrations

if [ $? -ne 0 ]; then
    echo "❌ ERROR: Migrations failed! Deployment halted."
    exit 1
fi

echo "✅ Migrations successful. Starting the application..."
docker compose up -d fastapi-app db

echo "--- Deployment Status ---"
docker compose ps
