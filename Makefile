# Enable more strict mode for shell
.SHELLFLAGS := -eu -c

# developer utilities
DOCKERBUILD := docker build --build-arg http_proxy=$$http_proxy --build-arg https_proxy=$$https_proxy

.PHONY: docs ruff virtualenv check_for_npm pyinstaller

ifdef VENV_PY_VERSION
export UV_PYTHON ?= $(VENV_PY_VERSION)
endif
UV := uv
UV_SYNC := $(UV) sync --frozen
UV_RUN := $(UV) run --no-sync
NPM := $(shell which npm)
MYPY := $(UV_RUN) mypy --sqlite-cache

check_for_npm:
	@if [ "$(NPM)" = "" ]; then echo "npm is not installed" ; exit 1; fi

WWW_PKGS := www/base www/console_view www/grid_view www/waterfall_view www/wsgi_dashboards www/badges
WWW_EX_PKGS := www/nestedexample
WWW_DEP_PKGS := www/plugin_support www/data-module www/ui
ALL_PKGS := master worker $(WWW_PKGS)

WWW_PKGS_FOR_UNIT_TESTS := $(filter-out www/badges www/plugin_support www/wsgi_dashboards, $(WWW_DEP_PKGS) $(WWW_PKGS))
WWW_PKGS_FOR_PRETTIER := $(filter-out www/plugin_support www/badges, $(WWW_DEP_PKGS) $(WWW_PKGS))
WWW_PKGS_FOR_NPM_BUILD := $(filter-out www/badges, $(WWW_PKGS))
ALL_PKGS_TARGETS := $(addsuffix _pkg,$(ALL_PKGS))
.PHONY: $(ALL_PKGS_TARGETS)

# build rst documentation
docs:
	$(UV_RUN) $(MAKE) -C master/docs dev
	@echo "You can now open master/docs/_build/html/index.html"

docs-towncrier:
	# Check that master/docs/relnotes/index.rst is not already generated (so it's in the staging area).
	# If docs-release and docs-release-spelling are called one after the other, then towncrier will report duplicate release notes.
	if ! git diff --name-only --cached | grep -q "master/docs/relnotes/index.rst"; then \
	$(UV_RUN) towncrier --draft | grep  'No significant changes.' || yes n | $(UV_RUN) towncrier ;\
	fi

docs-spelling:
	$(UV_RUN) $(MAKE) -C master/docs SPHINXOPTS=-W spelling

docs-linkcheck:
	$(UV_RUN) $(MAKE) -C master/docs SPHINXOPTS=-q linkcheck

docs-release: docs-towncrier
	$(UV_RUN) $(MAKE) -C master/docs

docs-release-spelling: docs-towncrier
	$(UV_RUN) $(MAKE) -C master/docs SPHINXOPTS=-W spelling

frontend_npm_install: check_for_npm
	cd www && $(NPM) ci

frontend_deps: frontend_npm_install check_for_npm
	for i in $(WWW_DEP_PKGS); \
		do (cd $$i; $(NPM) run build); done

frontend_tests: frontend_deps check_for_npm
	for i in $(WWW_PKGS_FOR_UNIT_TESTS); \
		do (cd $$i; $(NPM) run build-dev || exit 1; $(NPM) run test || exit 1) || exit 1; done

frontend_build: frontend_deps
	for i in $(WWW_PKGS_FOR_NPM_BUILD); \
		do (cd $$i; $(NPM) run build); done

# rebuild front-end from source
frontend: virtualenv frontend_build
	for i in $(WWW_PKGS); do $(UV) pip install -e $$i || exit 1; done

# build frontend wheels for installation elsewhere
frontend_wheels: frontend_build
	for i in $(WWW_PKGS); \
		do (cd $$i; $(UV) build --wheel || exit 1) || exit 1; done

# upgrade FE dependencies
frontend_npm_upgrade: check_for_npm
	cd www && rm -f package-lock.json && $(NPM) install

# install git hooks for validating patches at commit time
hooks:
	cp common/hooks/* `git rev-parse --git-dir`/hooks
rmpyc:
	find master worker \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -v {} \;

prettier-check: check_for_npm
	for subdir in $(WWW_PKGS_FOR_PRETTIER); do \
		( \
		cd $$subdir && \
		echo "Running prettier in $$subdir" && \
		$(NPM) exec -- prettier --check src *.ts *.js \
		) \
	done

prettier: check_for_npm
	for subdir in $(WWW_PKGS_FOR_PRETTIER); do \
		( \
		cd $$subdir && \
		echo "Running prettier in $$subdir" && \
		$(NPM) exec -- prettier --write src *.ts *.js \
		) \
	done

ruff:
	ruff format .

mypy-master-linux:
	$(MYPY) --cache-dir ".mypy_cache/master/linux" --platform linux --config-file ./pyproject.toml $(MYPY_EXTRA_FLAGS) master/buildbot
mypy-master-win32:
	$(MYPY) --cache-dir ".mypy_cache/master/win32" --platform win32 --config-file ./pyproject.toml $(MYPY_EXTRA_FLAGS) master/buildbot
mypy-worker-linux:
	$(MYPY) --cache-dir ".mypy_cache/worker/linux" --platform linux --config-file ./worker/.mypy.ini $(MYPY_EXTRA_FLAGS) worker/buildbot_worker
mypy-worker-win32:
	$(MYPY) --cache-dir ".mypy_cache/worker/win32" --platform win32 --config-file ./worker/.mypy.ini $(MYPY_EXTRA_FLAGS) worker/buildbot_worker

mypy: mypy-master-linux mypy-master-win32 mypy-worker-linux mypy-worker-win32

docker: docker-buildbot-worker docker-buildbot-master
	echo done
docker-buildbot-worker:
	$(DOCKERBUILD) -t buildbot/buildbot-worker:master -f Dockerfile.worker .
docker-buildbot-worker-node:
	$(DOCKERBUILD) -t buildbot/buildbot-worker-node:master master/contrib/docker/pythonnode_worker
docker-buildbot-master:
	$(DOCKERBUILD) -t buildbot/buildbot-master:master -f Dockerfile.master .

# helper for virtualenv creation
virtualenv:   # usage: make virtualenv VENV_PY_VERSION=python3.10
	$(UV_SYNC)

TRIALOPTS?=buildbot

.PHONY: trial
trial:
	$(UV_RUN) trial $(TRIALOPTS)

release_notes: virtualenv
	test ! -z "$(VERSION)"  #  usage: make release_notes VERSION=0.9.2
	$(UV_RUN) towncrier build --yes  --version $(VERSION) --date `date -u  +%F`
	git commit -m "Release notes for $(VERSION)"

$(ALL_PKGS_TARGETS): cleanup_for_tarballs frontend_build
	./common/maketarball.sh $(patsubst %_pkg,%,$@)

cleanup_for_tarballs:
	find master worker www -name VERSION -exec rm {} \;
	rm -rf dist
	mkdir dist
.PHONY: cleanup_for_tarballs
tarballs: $(ALL_PKGS_TARGETS)
.PHONY: tarballs

# helper for release creation
release: virtualenv
	test ! -z "$(VERSION)"  #  usage: make release VERSION=0.9.2
	test -d "../bbdocs/.git"  #  make release should be done with bbdocs populated at the same level as buildbot dir
	GPG_TTY=`tty` git tag -a -sf v$(VERSION) -m "TAG $(VERSION)"
	git push buildbot "v$(VERSION)"  # tarballs are made by circleci.yml, and create a github release
	export VERSION=$(VERSION) ; $(UV_RUN) make docs-release
	rm -rf ../bbdocs/docs/$(VERSION)  # in case of re-run
	cp -r master/docs/_build/html ../bbdocs/docs/$(VERSION)
	cd ../bbdocs && git pull && make && git add docs && git commit -m $(VERSION) && git push
	@echo When tarballs have been generated by github workflow 'release':
	@echo make finishrelease

finishrelease:
	rm -rf dist
	python3 ./common/download_release.py
	rm -rf ./dist/v*
	twine upload dist/*

# own venv to not break dev venv with non-editable install
pyinstaller: export UV_PROJECT_ENVIRONMENT := .venv-pyinstaller
pyinstaller:
#	PyInstaller can't follow the import hooks of editable installs
	$(UV_SYNC) --group pyinstaller --no-editable
	$(UV_RUN) pyinstaller pyinstaller/buildbot-worker.spec
