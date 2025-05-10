.. _Writing-a-New-Latent-Worker-Implementation:

Writing a New Latent Worker Implementation
------------------------------------------

Writing a new latent worker should only require subclassing
:class:`buildbot.worker.AbstractLatentWorker` and implementing :meth:`start_instance` and
:meth:`stop_instance` at a minimum.

.. bb:worker:: AbstractWorkerController

AbstractLatentWorker
~~~~~~~~~~~~~~~~~~~~

.. py:class:: buildbot.worker.AbstractLatentWorker

This class is the base class of all latent workers and implements some common functionality.
A custom worker should only need to override :meth:`start_instance` and :meth:`stop_instance` methods.

See :class:`buildbot.worker.ec2.EC2LatentWorker` for an example.

Additionally, :meth:`builds_may_be_incompatible` and :attr:`isCompatibleWithBuild` members must be
overridden if some qualities of the new instances is determined dynamically according to the
properties of an incoming build. An example a build may require a certain Docker image or amount of
allocated memory. Overriding these members ensures that builds aren't ran on incompatible workers
that have already been started.

    .. py:method:: start_instance(self)

        This method is responsible for starting instance that will try to connect with this master.
        A deferred should be returned.

        Any problems should use an errback or exception. When the error is likely related to
        infrastructure problem and the worker should be paused in case it produces too many errors,
        then ``LatentWorkerFailedToSubstantiate`` should be thrown. When the error is related to
        the properties of the build request, such as renderable Docker image, then
        ``LatentWorkerCannotSubstantiate`` should be thrown.

        The callback value can be ``None``, or can be an iterable of short strings to include in
        the "substantiate success" status message, such as identifying the instance that started.
        Buildbot will ensure that a single worker will never have its ``start_instance`` called
        before any previous calls to ``start_instance`` or ``stop_instance`` finish. Additionally,
        for each ``start_instance`` call, exactly one corresponding call to ``stop_instance`` will
        be done eventually.

    .. py:method:: stop_instance(self, fast=False)

        This method is responsible for shutting down instance. A deferred should be returned. If
        ``fast`` is ``True`` then the function should call back as soon as it is safe to do so, as,
        for example, the master may be shutting down. The value returned by the callback is
        ignored. Buildbot will ensure that a single worker will never have its ``stop_instance``
        called before any previous calls to ``stop_instance`` finish. During master shutdown any
        pending calls to ``start_instance`` or ``stop_instance`` will be waited upon finish.

    .. py:attribute:: builds_may_be_incompatible

        Determines if new instances have qualities dependent on the build. If ``True``, the master
        will call ``isCompatibleWithBuild`` to determine whether new builds are compatible with the
        started instance. Unnecessarily setting ``builds_may_be_incompatible`` to ``True`` may
        result in unnecessary overhead when processing the builds. By default, this is ``False``.

    .. py:method:: isCompatibleWithBuild(self, build_props)

        This method determines whether a started instance is compatible with the build that is
        about to be started. ``build_props`` is the properties of the build that are known before
        the build has been started. A build may be incompatible with already started instance if,
        for example, it requests a different amount of memory or a different Docker image. A
        deferred should be returned, whose callback should return ``True`` if build is compatible
        and ``False`` otherwise. The method may be called when the instance is not yet started and
        should indicate compatible build in that case. In the default implementation the callback
        returns ``True``.

    .. py:method:: check_instance(self)

        This method determines the health of an instance. The method is expected to return a tuple
        with two members: ``is_good`` and ``message``. The first member identifies whether the
        instance is still valid. It should be ``False`` if the method determined that a serious
        error has occurred and worker will not connect to the master. In such case, ``message``
        should identify any additional error message that should be displayed to Buildbot user.

        In case there is no additional messages, ``message`` should be an empty string.

        Any exceptions raised from this method are interpreted as if the method returned ``False``.
