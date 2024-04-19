# Enable more strict mode for shell
.SHELLFLAGS := -eu -c

# developer utilities
DOCKERBUILD := docker build --build-arg http_proxy=$$http_proxy --build-arg https_proxy=$$https_proxy
ROOT_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

.PHONY: docs pylint ruff virtualenv

ifeq ($(OS),Windows_NT)
  VENV_BIN_DIR := Scripts
  VENV_PY_VERSION ?= python
  VENV_CREATE := python -m venv
else
  VENV_BIN_DIR := bin
  VENV_PY_VERSION ?= python3
  VENV_CREATE := virtualenv -p $(VENV_PY_VERSION)
endif

VENV_NAME := .venv$(VENV_PY_VERSION)
PIP ?= $(ROOT_DIR)/$(VENV_NAME)/$(VENV_BIN_DIR)/pip
VENV_PYTHON ?= $(ROOT_DIR)/$(VENV_NAME)/$(VENV_BIN_DIR)/python
YARN := $(shell which yarnpkg || which yarn)

WWW_PKGS := www/react-base www/react-console_view www/react-grid_view www/react-waterfall_view www/react-wsgi_dashboards www/badges
WWW_EX_PKGS := www/nestedexample www/codeparameter
WWW_DEP_PKGS := www/plugin_support www/react-data-module www/react-ui
ALL_PKGS := master worker pkg $(WWW_PKGS)

WWW_PKGS_FOR_UNIT_TESTS := $(filter-out www/badges www/plugin_support www/react-ui www/react-grid_view www/react-wsgi_dashboards, $(WWW_DEP_PKGS) $(WWW_PKGS))

ALL_PKGS_TARGETS := $(addsuffix _pkg,$(ALL_PKGS))
.PHONY: $(ALL_PKGS_TARGETS)

# build rst documentation
docs:
	$(MAKE) -C master/docs dev
	@echo "You can now open master/docs/_build/html/index.html"

docs-towncrier:
	# Check that master/docs/relnotes/index.rst is not already generated (so it's in the staging area).
	# If docs-release and docs-release-spelling are called one after the other, then towncrier will report duplicate release notes.
	if ! git diff --name-only --cached | grep -q "master/docs/relnotes/index.rst"; then \
	if command -v towncrier >/dev/null 2>&1 ;\
	then \
	towncrier --draft | grep  'No significant changes.' || yes n | towncrier ;\
	fi \
	fi

docs-spelling:
	$(MAKE) -C master/docs SPHINXOPTS=-W spelling

docs-linkcheck:
	$(MAKE) -C master/docs SPHINXOPTS=-q linkcheck

docs-release: docs-towncrier
	$(MAKE) -C master/docs

docs-release-spelling: docs-towncrier
	$(MAKE) -C master/docs SPHINXOPTS=-W spelling

# pylint the whole sourcecode (validate.sh will do that as well, but only process the modified files)
pylint:
	$(MAKE) -C master pylint; master_res=$$?; \
	$(MAKE) -C worker pylint; worker_res=$$?; \
	if [ $$master_res != 0 ] || [ $$worker_res != 0 ]; then exit 1; fi

frontend_deps: $(VENV_NAME)
	$(PIP) install build wheel -r requirements-ci.txt
	for i in $(WWW_DEP_PKGS); \
		do (cd $$i; $(YARN) install --pure-lockfile; $(YARN) run build); done

frontend_tests: frontend_deps
	for i in $(WWW_PKGS); \
		do (cd $$i; $(YARN) install --pure-lockfile); done
	for i in $(WWW_PKGS_FOR_UNIT_TESTS); \
		do (cd $$i; $(YARN) run build-dev || exit 1; $(YARN) run test || exit 1) || exit 1; done

# rebuild front-end from source
frontend: frontend_deps
	for i in pkg $(WWW_PKGS); do $(PIP) install -e $$i || exit 1; done

# build frontend wheels for installation elsewhere
frontend_wheels: frontend_deps
	for i in pkg $(WWW_PKGS); \
		do (cd $$i; $(VENV_PYTHON) -m build --no-isolation --wheel || exit 1) || exit 1; done

# do installation tests. Test front-end can build and install for all install methods
frontend_install_tests: frontend_deps
	trial pkg/test_buildbot_pkg.py

# upgrade FE dependencies
frontend_yarn_upgrade:
	for i in $(WWW_PKGS) $(WWW_EX_PKGS) $(WWW_DEP_PKGS); \
		do (cd $$i; echo $$i; rm -rf yarn.lock; $(YARN) install || echo $$i failed); done

# install git hooks for validating patches at commit time
hooks:
	cp common/hooks/* `git rev-parse --git-dir`/hooks
rmpyc:
	find master worker \( -name '*.pyc' -o -name '*.pyo' \) -exec rm -v {} \;

ruff:
	ruff --fix .

docker: docker-buildbot-worker docker-buildbot-master
	echo done
docker-buildbot-worker:
	$(DOCKERBUILD) -t buildbot/buildbot-worker:master worker
docker-buildbot-master:
	$(DOCKERBUILD) -t buildbot/buildbot-master:master master

$(VENV_NAME):
	$(VENV_CREATE) $(VENV_NAME)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(PIP) install -U setuptools wheel

# helper for virtualenv creation
virtualenv: $(VENV_NAME)   # usage: make virtualenv VENV_PY_VERSION=python3.4
	$(PIP) install -r requirements-ci.txt \
		-r requirements-ciworker.txt \
		-r requirements-cidocs.txt \
		packaging towncrier
	@echo now you can type following command  to activate your virtualenv
	@echo . $(VENV_NAME)/$(VENV_BIN_DIR)/activate

TRIALOPTS?=buildbot

.PHONY: trial
trial: virtualenv
	. $(VENV_NAME)/$(VENV_BIN_DIR)/activate && trial $(TRIALOPTS)

release_notes: $(VENV_NAME)
	test ! -z "$(VERSION)"  #  usage: make release_notes VERSION=0.9.2
	towncrier build --yes  --version $(VERSION) --date `date -u  +%F`
	git commit -m "Release notes for $(VERSION)"

$(ALL_PKGS_TARGETS): cleanup_for_tarballs frontend_deps
	. $(VENV_NAME)/$(VENV_BIN_DIR)/activate && ./common/maketarball.sh $(patsubst %_pkg,%,$@)

cleanup_for_tarballs:
	find master pkg worker www -name VERSION -exec rm {} \;
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
	export VERSION=$(VERSION) ; . .venv/bin/activate && make docs-release
	rm -rf ../bbdocs/docs/$(VERSION)  # in case of re-run
	cp -r master/docs/_build/html ../bbdocs/docs/$(VERSION)
	cd ../bbdocs && git pull
	. .venv/bin/activate && cd ../bbdocs && make && git add docs && git commit -m $(VERSION) && git push
	@echo When tarballs have been generated by circleci:
	@echo make finishrelease

finishrelease:
	rm -rf dist
	python3 ./common/download_release.py
	rm -rf ./dist/v*
	twine upload --sign dist/*

pyinstaller: virtualenv
	$(PIP) install pyinstaller
	$(VENV_NAME)/$(VENV_BIN_DIR)/pyinstaller pyinstaller/buildbot-worker.spec
