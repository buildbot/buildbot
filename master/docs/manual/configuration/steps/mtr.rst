.. bb:step:: MTR

.. _Step-MTR:

MTR (mysql-test-run)
++++++++++++++++++++

The :bb:step:`MTR` class is a subclass of :bb:step:`Test`.
It is used to run test suites using the mysql-test-run program, as used in MySQL, Drizzle, MariaDB, and MySQL storage engine plugins.

The shell command to run the test suite is specified in the same way as for the :bb:step:`Test` class.
The :bb:step:`MTR` class will parse the output of running the test suite, and use the count of tests executed so far to provide more accurate completion time estimates.
Any test failures that occur during the test are summarized on the Waterfall Display.

Server error logs are added as additional log files, useful to debug test failures.

Optionally, data about the test run and any test failures can be inserted into a database for further analysis and report generation.
To use this facility, create an instance of :class:`twisted.enterprise.adbapi.ConnectionPool` with connections to the database.
The necessary tables can be created automatically by setting ``autoCreateTables`` to ``True``, or manually using the SQL found in the :src:`mtrlogobserver.py <master/buildbot/steps/mtrlogobserver.py>` source file.

One problem with specifying a database is that each reload of the configuration will get a new instance of ``ConnectionPool`` (even if the connection parameters are the same).
To avoid that Buildbot thinks the builder configuration has changed because of this, use the :class:`steps.mtrlogobserver.EqConnectionPool` subclass of :class:`ConnectionPool`, which implements an equality operation that avoids this problem.

Example use:

.. code-block:: python

    from buildbot.plugins import steps, util

    myPool = util.EqConnectionPool("MySQLdb", "host", "buildbot", "password", "db")
    myFactory.addStep(steps.MTR(workdir="mysql-test", dbpool=myPool,
                                command=["perl", "mysql-test-run.pl", "--force"]))

The :bb:step:`MTR` step's arguments are:

``textLimit``
    Maximum number of test failures to show on the waterfall page (to not flood the page in case of a large number of test failures.
    Defaults to 5.

``testNameLimit``
    Maximum length of test names to show unabbreviated in the waterfall page, to avoid excessive column width.
    Defaults to 16.

``parallel``
    Value of option `--parallel` option used for :file:`mysql-test-run.pl` (number of processes used to run the test suite in parallel).
    Defaults to 4.
    This is used to determine the number of server error log files to download from the worker.
    Specifying a too high value does not hurt (as nonexistent error logs will be ignored), however if using option `--parallel` value greater than the default it needs to be specified, or some server error logs will be missing.

``dbpool``
    An instance of :class:`twisted.enterprise.adbapi.ConnectionPool`, or ``None``.
    Defaults to ``None``.
    If specified, results are inserted into the database using the :class:`ConnectionPool`.

``autoCreateTables``
    Boolean, defaults to ``False``.
    If ``True`` (and ``dbpool`` is specified), the necessary database tables will be created automatically if they do not exist already.
    Alternatively, the tables can be created manually from the SQL statements found in the :src:`mtrlogobserver.py <master/buildbot/steps/mtrlogobserver.py>` source file.

``test_type``
    Short string that will be inserted into the database in the row for the test run.
    Defaults to the empty string, but can be specified to identify different types of test runs.

``test_info``
    Descriptive string that will be inserted into the database in the row for the test run.
    Defaults to the empty string, but can be specified as a user-readable description of this particular test run.

``mtr_subdir``
    The subdirectory in which to look for server error log files.
    Defaults to :file:`mysql-test`, which is usually correct.
    :ref:`Interpolate` is supported.
