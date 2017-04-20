Builds ``state_string`` is now automatically computed according to the :py:meth:`BuildStep.getResultSummary`,  :py:attr:`BuildStep.description` and ``updateBuildSummaryPolicy`` from :ref:`Buildstep-Common-Parameters`.
This allows the dashboards and reporters to get a descent summary text of the build without fetching the steps.
