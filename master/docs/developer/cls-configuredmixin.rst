IConfigured
===========

.. class:: buildbot.interfaces.IConfigured

    Providers of this interface allow get and set access to an object configuration

    The goal is to be able to have a way to serialize all configured stuff for display by the UI, UI-plugins, or status plugins.

   .. method:: getConfigDict()

        this method should be overridden in order to describe the public configuration of the object

ConfiguredMixin
===============

.. py:module:: buildbot.util

.. py:class:: ConfiguredMixin

    .. py:attribute:: name

        Each object configured shall have a ``name``, defined as a class attribute

    .. py:method:: getConfigDict(self)

        the default method returns a dict with only the name attribute
