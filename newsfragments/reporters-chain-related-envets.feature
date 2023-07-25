Only related events are now serialized (chained) in ``ReporterBase._got_event`` to preserve correct processing order.
This can improve performance of reporters on bigger Buildbot instances or reporters with slower generators.
