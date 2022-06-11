.. _Test-TestBuildStepMixin:

TestBuildStepMixin
++++++++++++++++++

.. py:class:: buildbot.test.steps.TestBuildStepMixin

    The class :class:`TestBuildStepMixin` allows to test build steps.
    It mocks the connection to the worker.
    The commands sent to the worker can be verified and command results can be injected back into the step under test.
    Additionally, the step under test is modified to allow checking how the step runs and what results it produces.

    The following is an example of a basic step test:

    .. code-block:: python

        class RemovePYCs(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

            def setUp(self):
                self.setup_test_reactor()
                return self.setup_test_build_step()

            def tearDown(self):
                return self.tear_down_test_build_step()

            @defer.inlineCallbacks
            def test_run_ok(self):
                self.setup_step(python_twisted.RemovePYCs())
                self.expect_commands(
                    ExpectShell(workdir='wkdir',
                                command=['find', '.', '-name', '\'*.pyc\'', '-exec', 'rm', '{}', ';'])
                    .exit(0)
                )
                self.expect_outcome(result=SUCCESS, state_string='remove .pycs')
                return self.run_step()

    Basic workflow is as follows:

     * The test case must derive from ``TestReactorMixin`` and properly setup it.

     * In ``setUp()`` of test case call ``self.setup_test_build_step()``.

     * In unit test call ``self.setup_step(step)`` which will setup the step for testing.

     * Call ``self.expect_commands(commands)`` to specify commands that the step is expected to run and the results of these commands.

     * Call various other ``expect_*`` member functions to define other expectations.

     * Call ``self.run_step()`` to actually run the step.

    All expectations are verified once the step has completed running.

    .. py:method:: setup_test_build_step()

        Call this function in the ``setUp()`` method of the test case to setup step testing machinery.

    .. py:method:: tear_down_test_build_step()

        Call this function in the ``tearDown()`` of the test case to destroy step testing machinery.

    .. py:method:: setup_step(step, worker_env=None, build_files=None)

        :param dict worker_env: An optional dictionary of environment variables on the mock worker.
        :param list build_files: An optional list of source files that were changed in the build.
        :returns: An instance of prepared step (not the same as the ``step`` argument).

        Prepares the given step for testing.
        The method mimics how Buildbot instantiates steps in reality and thus the ``step`` parameter is used only as a factory for creating the real step.

    .. py:attribute:: step

        The step under test.
        This attribute is available after ``setup_step()`` is run.

    ..
        TODO: build, progress, worker, properties attributes

    .. py:method:: expect_commands(*commands)

        :param commands: A list of commands that are expected to be run (a subclass of :class:`buildbot.test.steps.Expect`).

        Sets up an expectation of step sending the given commands to worker.

    .. py:method:: expect_outcome(result, state_string=None)

        :param result: A result from `buildbot.process.results`.
        :param str state_string: An optional status text.

        Sets up an expectation of the step result.

    .. py:method:: expect_property(property, value, source=None)

        :param str property: The name of the property
        :param str value: The value of the property
        :param str source: An optional source of the property

        Sets up an expectation of a property set by the step

    .. py:method:: expect_no_property(self, property)

        :param str property: The name of the property

        Sets up an expectation of an absence of a property set by the step.

    .. py:method:: expect_log_file(self, logfile, contents)

        :param str logfile: The name of the log file
        :param str contents: The contents of the log file

        Sets up an expectation of a log file being produced by the step.
        Only the ``stdout`` associated with the log file is checked.
        To check the ``stderr`` see ``expect_log_file_stderr()``

    .. py:method:: expect_log_file_stderr(self, logfile, contents)

        :param str logfile: The name of the log file
        :param str contents: The contents of the log file

        Sets up an expectation of a ``stderr`` output in log file being produced by the step.

    .. py:method:: expect_build_data(name, value, source)

        :param str name: The name of the build data.
        :param str value: The value of the build data.
        :param str source: The source of the build data.

        Sets up an expectation of build data produced by the step.

    .. py:method:: expect_hidden(hidden=True)

        :param bool hidden: Whether the step should be hidden.

        Sets up an expectation of step being hidden on completion.

    .. py:method:: expect_exception(expection_class)

        :param expection_class: The type of the class to expect.

        Sets up an expectation of an exception being raised during the runtime of the step.
        The expected result of the step is automatically set to ``EXCEPTION``.

    ..
        TODO: expect_test_result_sets(), expect_test_results()

        These are not documented yet as there's no UI to view them.

    .. py:method:: run_step()

        Runs the step and validates the expectations setup before this function.
