.. _Requirements:

Requirements
============

.. _Common-Requirements:

Common Requirements
-------------------

At a bare minimum, you'll need the following for both the buildmaster and a worker:

Python: https://www.python.org

  Buildbot master works with Python-3.8+.
  Buildbot worker works with Python-3.7+.

  .. note::

    This should be a "normal" build of Python.
    Builds of Python with debugging enabled or other unusual build parameters are likely to cause incorrect behavior.

Twisted: http://twistedmatrix.com

  Buildbot requires Twisted-17.9.0 or later on the master and the worker.
  In upcoming versions of Buildbot, a newer Twisted will also be required on the worker.
  As always, the most recent version is recommended.

Certifi: https://github.com/certifi/python-certifi

  Certifi provides collection of Root Certificates for validating the trustworthiness of SSL certificates. 
  Unfortunately it does not support any addition of own company certificates.
  At the moment you need to add your own .PEM content to cacert.pem manually.

Of course, your project's build process will impose additional requirements on the workers.
These hosts must have all the tools necessary to compile and test your project's source code.

.. note::

  If your internet connection is secured by a proxy server, please check your ``http_proxy`` and ``https_proxy`` environment variables.
  Otherwise ``pip`` and other tools will fail to work.

Windows Support
~~~~~~~~~~~~~~~

Buildbot - both master and worker - runs well natively on Windows.
The worker runs well on Cygwin, but because of problems with SQLite on Cygwin, the master does not.

Buildbot's windows testing is limited to the most recent Twisted and Python versions.
For best results, use the most recent available versions of these libraries on Windows.

Pywin32: http://sourceforge.net/projects/pywin32/

  Twisted requires PyWin32 in order to spawn processes on Windows.

Build Tools for Visual Studio 2019 - Microsoft Visual C++ compiler

  Twisted requires MSVC to compile some parts like tls during the installation, 
  see https://twistedmatrix.com/trac/wiki/WindowsBuilds and https://wiki.python.org/moin/WindowsCompilers.
