Worker command expectations
+++++++++++++++++++++++++++

:class:`TestBuildStepMixin` is used to test steps and accepts command expectations to its ``expect_commands`` method.
These command expectations are instances of classes listed in this page.

In all cases the arguments used to construct the expectation is what is expected to receive from the step under test.
The methods called on the command are used to build a list of effects that the step will observe.


.. py:class:: buildbot.test.steps.Expect

    This class is the base class of all command expectation classes.
    It must not be instantiated by the user.
    It provides methods that are common to all command expectations.

    .. py:method:: exit(code)

        :param int code: Exit code

        Specifies command exit code sent to the step.
        In most cases ``0`` signify success, other values signify failure.

    .. py:method:: stdout(output)

        :param output: stdout output to send to the step. Must be an instance of ``bytes`` or ``str``.

        Specifies ``stdout`` stream in the ``stdio`` log that is sent by the command to the step.

    .. py:method:: stderr(output)

        :param output: stderr output to send to the step. Must be an instance of ``bytes`` or ``str``.

        Specifies ``stderr`` stream in the ``stdio`` log that is sent by the command to the step.

    .. py:method:: log(name, **streams)

        :param str name: The name of the log.
        :param kwargs streams: The log streams of the log streams.
                               The most common are ``stdout`` and ``stderr``.
                               The values must be instances of ``bytes`` or ``str``.

        Specifies logs sent by the command to the step.

        For ``stdio`` log and ``stdout`` stream use the ``stdout()`` function.

        For ``stdio`` log and ``stderr`` stream use the ``stderr()`` function.

    .. py:method:: error(error)

        :param error: An instance of an exception to throw when running the command.

        Throws an exception when running the command.
        This is often used to simulate broken connection by throwing in an instance of ``twisted.internet.error.ConnectionLost``.


.. _Test-ExpectShell:

ExpectShell
~~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectShell(Expect)

    This class represents a ``shell`` command sent to the worker.

    Usually the stdout log produced by the command is specified by the ``.stdout`` method, the stderr log is specified by the ``.stderr`` method and the exit code is specified by the ``.exit`` method.

    .. code-block:: python

        ExpectShell(workdir='myworkdir', command=["my-test-command", "arg1", "arg2"])
        .stdout(b'my sample output')
        .exit(0)

    .. py:method:: __init__(workdir, command, env=None, want_stdout=1, want_stderr=1, initial_stdin=None, timeout=20 * 60, max_time=None, sigterm_time=None, logfiles=None, use_pty=None, log_environ=True, interrupt_signal=None)

        Initializes the expectation.


.. _Test-ExpectStat:

ExpectStat
~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectStat(Expect)

    This class represents a ``stat`` command sent to the worker.

    Tests usually indicate the existence of the file by calling the ``.exit`` method.

    .. py:method:: __init__(file, workdir=None, log_environ=None)

        Initializes the expectation.

    .. py:method:: stat(mode, inode=99, dev=99, nlink=1, uid=0, gid=0, size=99, atime=0, mtime=0, ctime=0)

        Specifies ``os.stat`` result that is sent back to the step.

        In most cases it's more convenient to use ``stat_file`` or ``stat_dir``.

    .. py:method:: stat_file(mode=0, size=99, atime=0, mtime=0, ctime=0)

        :param int mode: Additional mode bits to set

        Specifies ``os.stat`` result of a regular file.

    .. py:method:: stat_dir(mode=0, size=99, atime=0, mtime=0, ctime=0)

        :param int mode: Additional mode bits to set

        Specifies ``os.stat`` result of a directory.


.. _Test-ExpectUploadFile:

ExpectUploadFile
~~~~~~~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectUploadFile(Expect)

    This class represents a ``uploadFile`` command sent to the worker.

    .. py:method:: __init__(blocksize=None, maxsize=None, workersrc=None, workdir=None, writer=None, keepstamp=None, slavesrc=None, interrupted=False)

        Initializes the expectation.

    .. py:method:: upload_string(string, error=None)

        :param str string: The data of the file to sent to the step.
        :param object error: An optional instance of an exception to raise to simulate failure to transfer data.

        Specifies the data to send to the step.


.. _Test-ExpectDownloadFile:

ExpectDownloadFile
~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectDownloadFile(Expect)

    This class represents a ``downloadFile`` command sent to the worker.
    Tests usually check what the step attempts to send to the worker by calling ``.download_string`` and checking what data the supplied callable receives.

    .. py:method:: __init__(blocksize=None, maxsize=None, workerdest=None, workdir=None, reader=None, mode=None, interrupted=False, slavesrc=None, slavedest=None)

        Initializes the expectation.

    .. py:method:: download_string(dest_callable, size=1000)

        :param callable dest_callable: A callable to call with the data that is being sent from the step.
        :param int size: The size of the data to read

        Specifies the callable to store the data that the step wants the worker to download.


.. _Test-ExpectMkdir:

ExpectMkdir
~~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectMkdir(Expect)

    This class represents a ``mkdir`` command sent to the worker.

    .. py:method:: __init__(dir=None, log_environ=None))

        Initializes the expectation.


.. _Test-ExpectRmdir:

ExpectRmdir
~~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectRmdir(Expect)

    This class represents a ``rmdir`` command sent to the worker.

    .. py:method:: __init__(dir=None, log_environ=None, timeout=None, path=None)

        Initializes the expectation.


.. _Test-ExpectCpdir:

ExpectCpdir
~~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectCpdir(Expect)

    This class represents a ``cpdir`` command sent to the worker.

    .. py:method:: __init__(fromdir=None, todir=None, log_environ=None, timeout=None, max_time=None)

        Initializes the expectation.


.. _Test-ExpectRmfile:

ExpectRmfile
~~~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectRmfile(Expect)

    This class represents a ``rmfile`` command sent to the worker.

    .. py:method:: __init__(path=None, log_environ=None)

        Initializes the expectation.

.. _Test-ExpectGlob:

ExpectGlob
~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectGlob(Expect)

    This class represents a ``mkdir`` command sent to the worker.

    .. py:method:: __init__(path=None, log_environ=None)

        Initializes the expectation.

    .. py:method:: files(files=None)

        :param list files: An optional list of returned files.

        Specifies the list of files returned to the step.

.. _Test-ExpectListdir:

ExpectListdir
~~~~~~~~~~~~~

.. py:class:: buildbot.test.steps.ExpectListdir(Expect)

    This class represents a ``mkdir`` command sent to the worker.

    .. py:method:: __init__(dir=None):

        Initializes the expectation.

    .. py:method:: files(files=None)

        :param list files: An optional list of returned files.

        Specifies the list of files returned to the step.
