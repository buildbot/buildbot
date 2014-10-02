Introduction
============

This directory holds a bunch of DockerFiles with installation of buildbot from sources.

Those DockerFiles are not intended to be official deployment Docker images, but just a convenient way for the buildbot development team to verify that buildbot can be installed on various linux distributions

Creating new environment tests
==============================

If you need to report installation issues for buildbot, we would be grateful that you contribute to this directory by posting a Dockerfile which fails to install.
Please make sure the dependencies are correct, by looking at the DockerFile already written, and find equivalent for dependencies for your distro.
