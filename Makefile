# nullstar static site

PYTHON ?= python3
HOST ?= 127.0.0.1
PORT ?= 8033

.DEFAULT_GOAL := build
.PHONY: build serve check clean help

build:
	$(PYTHON) src/build.py

server: build
	$(PYTHON) src/server.py --host $(HOST) --port $(PORT)

check:
	$(PYTHON) src/check.py

clean:
	rm -rf dist dist.tmp src/__pycache__
	fuser -k -9 8033/tcp
