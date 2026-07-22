-include .env

WUV ?= $(wuv)

ifeq ($(strip $(WUV)),)
$(error WUV is not set. Copy .env.sample to .env and set WUV=/mnt/c/Users/<user>/.local/bin/uv.exe)
endif

main_file_name=earth_photo_manager
project_name=earth_photo_manager
target=$(project_name)/.built
target_zip=$(project_name).zip
srcs=$(wildcard *.py) $(wildcard *.pyw) $(wildcard src/*.py)
version=$(shell head -n1 version.txt 2>/dev/null || echo v0.1.0)
ZIP ?= 7z a -tzip -mx=1 -mmt=on

top: $(target_zip)
all: $(target_zip)

$(target_zip): $(target)
	@rm -rf $(target_zip)
	@$(ZIP) $(target_zip) $(project_name)

$(target): $(srcs) setup.py pyproject.toml version.txt $(wildcard .env)
	@rm -rf $(project_name)
	@$(WUV) run setup.py build
	@echo "不要なファイルを削除中..."
	@rm -f $(project_name)/lib/PySide6/Qt6WebEngine*.dll 2>/dev/null || true
	@touch $(target)

clean:
	@rm -rf $(target)
	@rm -rf build
	@rm -rf __pycache__ src/__pycache__

test:
	@$(WUV) run python $(main_file_name).pyw
