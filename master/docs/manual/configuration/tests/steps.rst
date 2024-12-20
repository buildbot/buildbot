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

            @defer.inlineCallbacks
            def setUp(self):
                yield self.setup_test_reactor()
                yield self.setup_test_build_step()

            @defer.inlineCallbacks
            def test_run_ok(self):
                self.setup_step(python_twisted.RemovePYCs())
                self.expect_commands(
                    ExpectShell(workdir='wkdir',
                                command=['find', '.', '-name', '\'*.pyc\'', '-exec', 'rm', '{}', ';'])
                    .exit(0)
                )
                self.expect_outcome(result=SUCCESS, state_string='remove .pycs')
                yield self.run_step()

    Basic workflow is as follows:

     * The test case must derive from ``TestReactorMixin`` and properly setup it.

     * In ``setUp()`` of test case call ``self.setup_test_build_step()``.

     * In unit test first optionally call ``self.setup_build(...)`` function to setup information
        that will be available to the step during the test.

     * In unit test call ``self.setup_step(step)`` which will setup the step for testing.

     * Call ``self.expect_commands(commands)`` to specify commands that the step is expected to run and the results of these commands.

     * Call various other ``expect_*`` member functions to define other expectations.

     * Call ``self.run_step()`` to actually run the step.

    All expectations are verified once the step has completed running.

    .. py:method:: setup_test_build_step()

        Call this function in the ``setUp()`` method of the test case to setup step testing machinery.

    .. py:method:: setup_build(worker_env=None, build_files=None)

        :param dict worker_env: An optional dictionary of environment variables on the mock worker.
        :param list build_files: An optional list of source files that were changed in the build.

        Sets up build and worker information that will be available to the tested step.

    .. py:method:: setup_step(step, worker_env=None, build_files=None)

        :param BuildStep step: An instance of ``BuildStep`` to test.
        :param dict worker_env: An optional dictionary of environment variables on the mock worker (deprecated).
        :param list build_files: An optional list of source files that were changed in the build (deprecated).
        :returns: An instance of prepared step (not the same as the ``step`` argument).

        Prepares the given step for testing. This function may be invoked multiple times.
        The ``step`` argument is used as a step factory, just like in real Buildbot.

    .. py:attribute:: step

        (deprecated) The step under test.
        This attribute is available after ``setup_step()`` is run.

        This function has been deprecated, use ``get_nth_step(0)`` as a replacement

    .. py:method:: get_nth_step(index)

        :param int index: The index of the step to retrieve

        Retrieves the instance of a step that has been created by ``setup_step()``.

    ..
        TODO: build, progress, worker attributes

    .. py:method:: expect_commands(*commands)

        :param commands: A list of commands that are expected to be run (a subclass of :class:`buildbot.test.steps.Expect`).

        Sets up an expectation of step sending the given commands to worker.

    .. py:method:: expect_outcome(result, state_string=None)

        :param result: A result from `buildbot.process.results`.
        :param str state_string: An optional status text.

        Sets up an expectation of the step result. If there are multiple steps registered to the
        test, then there must be as many calls to ``expect_outcome`` as there are steps, in the
        same order.

    .. py:method:: expect_property(property, value, source=None)

        :param str property: The name of the property
        :param str value: The value of the property
        :param str source: An optional source of the property

        Sets up an expectation of a property set by the step. If there are multiple steps
        registered to the test, then this function tests the cumulative set of properties set
        on the build.

    .. py:method:: expect_no_property(self, property)

        :param str property: The name of the property

        Sets up an expectation of an absence of a property set by the step. If there are multiple
        steps registered to the test, then this function expects that no tests set the property.

    .. py:method:: expect_log_file(self, logfile, contents, step_index=0)

        :param str logfile: The name of the log file
        :param str contents: The contents of the log file
        :param int step_index: The index of the step whose logs to investigate.

        Sets up an expectation of a log file being produced by the step.
        Only the ``stdout`` associated with the log file is checked.
        To check the ``stderr`` see ``expect_log_file_stderr()``

    .. py:method:: expect_log_file_stderr(self, logfile, contents, step_index=0)

        :param str logfile: The name of the log file
        :param str contents: The contents of the log file
        :param int step_index: The index of the step whose logs to investigate.

        Sets up an expectation of a ``stderr`` output in log file being produced by the step.

    .. py:method:: expect_build_data(name, value, source)

        :param str name: The name of the build data.
        :param str value: The value of the build data.
        :param str source: The source of the build data.

        Sets up an expectation of build data produced by the step. If there are multiple steps
        registered to the test, then this function tests the cumulative set of build data added to
        the build.

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

        Runs the steps and validates the expectations setup before this function.
