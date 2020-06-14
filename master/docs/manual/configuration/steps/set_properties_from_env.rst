.. bb:step:: SetPropertiesFromEnv

.. py:class:: buildbot.steps.worker.SetPropertiesFromEnv

.. _Step-SetPropertiesFromEnv:

SetPropertiesFromEnv
++++++++++++++++++++

Buildbot workers (later than version 0.8.3) provide their environment variables to the master on connect.
These can be copied into Buildbot properties with the :bb:step:`SetPropertiesFromEnv` step.
Pass a variable or list of variables in the ``variables`` parameter, then simply use the values as properties in a later step.

Note that on Windows, environment variables are case-insensitive, but Buildbot property names are case sensitive.
The property will have exactly the variable name you specify, even if the underlying environment variable is capitalized differently.
If, for example, you use ``variables=['Tmp']``, the result will be a property named ``Tmp``, even though the environment variable is displayed as :envvar:`TMP` in the Windows GUI.

.. code-block:: python

    from buildbot.plugins import steps, util

    f.addStep(steps.SetPropertiesFromEnv(variables=["SOME_JAVA_LIB_HOME", "JAVAC"]))
    f.addStep(steps.Compile(commands=[util.Interpolate("%(prop:JAVAC)s"),
                                      "-cp",
                                      util.Interpolate("%(prop:SOME_JAVA_LIB_HOME)s")]))

Note that this step requires that the worker be at least version 0.8.3.
For previous versions, no environment variables are available (the worker environment will appear to be empty).
