#!/bin/bash
mkdir -p output
rm output/* 2>/dev/null

echo "Compiling..."
env GOOS=linux GOARCH=amd64 go build -o output/server.bin server.go
env GOOS=windows GOARCH=amd64 go build  -o output/win_implant.exe implant.go
