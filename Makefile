# AAiOS Makefile — convenience wrapper around tasks.ps1 / tasks.sh
#
# Usage:
#   make help       # list targets
#   make dev        # start dev stack
#   make test       # run tests
#   make lint       # lint
#   make check      # lint + test + typecheck (run before pushing)
#   make build      # build artifacts
#
# This Makefile detects the OS and delegates to tasks.ps1 (Windows) or
# tasks.sh (Linux/macOS). On Windows, run from PowerShell.

# Detect OS
ifeq ($(OS),Windows_NT)
    TASKS = powershell -ExecutionPolicy Bypass -File ./tasks.ps1
else
    TASKS = ./tasks.sh
endif

.PHONY: help dev api web test test-unit test-integration test-e2e test-web \
        test-offline lint typecheck format check build build-wheel build-web \
        install-windows docker-up docker-down clean venv install doctor version

help:
	@$(TASKS) help

dev:
	@$(TASKS) dev

api:
	@$(TASKS) api

web:
	@$(TASKS) web

test:
	@$(TASKS) test

test-unit:
	@$(TASKS) test-unit

test-integration:
	@$(TASKS) test-integration

test-e2e:
	@$(TASKS) test-e2e

test-web:
	@$(TASKS) test-web

test-offline:
	@$(TASKS) test-offline

lint:
	@$(TASKS) lint

typecheck:
	@$(TASKS) typecheck

format:
	@$(TASKS) format

check:
	@$(TASKS) check

build:
	@$(TASKS) build

build-wheel:
	@$(TASKS) build-wheel

build-web:
	@$(TASKS) build-web

install-windows:
	@$(TASKS) install-windows

docker-up:
	@$(TASKS) docker-up

docker-down:
	@$(TASKS) docker-down

clean:
	@$(TASKS) clean

venv:
	@$(TASKS) venv

install:
	@$(TASKS) install

doctor:
	@$(TASKS) doctor

version:
	@$(TASKS) version
