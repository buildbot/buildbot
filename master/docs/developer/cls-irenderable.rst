.. index:: single: Properties; IRenderable

IRenderable
===========

.. class:: buildbot.interfaces.IRenderable::

    Providers of this class can be "rendered", based on available properties, when a build is started.

    .. method:: getRenderingFor(iprops)

        :param iprops: the :class:`~buildbot.interfaces.IProperties` provider supplying the properties of the build.

        Returns the interpretation of the given properties, optionally in a Deferred.
