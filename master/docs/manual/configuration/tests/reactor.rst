.. _Test-TestReactorMixin:

TestReactorMixin
++++++++++++++++

.. py:class:: buildbot.test.reactor.TestReactorMixin

    The class ``TestReactorMixin`` is used to create a fake ``twisted.internet.reactor`` in tests.
    This allows to mock the flow of time in tests.
    The fake reactor becomes available as ``self.reactor`` in the test case that mixes in ``TestReactorMixin``.

    Call ``self.reactor.advance(seconds)`` to advance the mocked time by the specified number of seconds.

    Call ``self.reactor.pump(seconds_list)`` to advance the mocked time multiple times as if by calling ``advance``.

    For more information see the documentation of `twisted.internet.task.Clock <https://twistedmatrix.com/documents/current/api/twisted.internet.task.Clock.html>`_.

    .. py:method:: setup_test_reactor(use_asyncio=False)

        :param bool use_asyncio Whether to enable asyncio integration.

        Call this function in the ``setUp()`` of the test case to setup fake reactor.
