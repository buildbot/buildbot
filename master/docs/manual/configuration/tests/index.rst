.. _Testing-Utilities:

Testing Utilities
=================

.. toctree::
    :hidden:
    :maxdepth: 2

    expect
    reactor
    steps

This section outlives various utilities that are useful when testing configuration written for Buildbot.

.. note::
    At this moment the APIs outlined here are experimental and subject to change.

* :ref:`Test-TestBuildStepMixin` - provides a framework for testing steps
* :ref:`Test-TestReactorMixin` - sets up test case with mock time

Command expectations:

* :ref:`Test-ExpectShell` - expects ``shell`` command
* :ref:`Test-ExpectStat` - expects ``stat`` command
* :ref:`Test-ExpectUploadFile` - expects ``uploadFile`` command
* :ref:`Test-ExpectDownloadFile` - expects ``downloadFile`` command
* :ref:`Test-ExpectMkdir` - expects ``mkdir`` command
* :ref:`Test-ExpectRmdir` - expects ``rmdir`` command
* :ref:`Test-ExpectCpdir` - expects ``cpdir`` command
* :ref:`Test-ExpectRmfile` - expects ``rmfile`` command
* :ref:`Test-ExpectGlob` - expects ``glob`` command
* :ref:`Test-ExpectListdir` - expects ``listdir`` command
