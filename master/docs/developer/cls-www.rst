Web Server Classes
==================

Most of the source in :src:`master/buildbot/www` is self-explanatory.
However, a few classes and methods deserve some special mention.

Resources
---------

.. py:module:: buildbot.www.resource

.. py:class:: Redirect(url)

    This is a subclass of Twisted Web's ``Error``.
    If this is raised within :py:meth:`~Resource.asyncRenderHelper`, the user will be redirected to the given URL.

.. py:class:: Resource

    This class specializes the usual Twisted Web ``Resource`` class.

    It adds support for resources getting notified when the master is reconfigured.

    .. py:attribute:: needsReconfig

        If True, :py:meth:`reconfigResource` will be called on reconfig.

    .. py:method:: reconfigResource(new_config)

        :param new_config: new :py:class:`~buildbot.config.MasterConfig` instance
        :returns: Deferred if desired

        Reconfigure this resource.

    It's surprisingly difficult to render a Twisted Web resource asynchronously.
    This method makes it quite a bit easier:

    .. py:method:: asyncRenderHelper(request, callable, writeError=None)

        :param request: the request instance
        :param callable: the render function
        :param writeError: optional callable for rendering errors

        This method will call ``callable``, which can return a Deferred, with the given ``request``.
        The value returned from this callable will be converted to an HTTP response.
        Exceptions, including ``Error`` subclasses, are handled properly.
        If the callable raises :py:class:`Redirect`, the response will be a suitable HTTP 302 redirect.

        Use this method as follows::

            def render_GET(self, request):
                return self.asyncRenderHelper(request, self.renderThing)
