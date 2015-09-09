.. _Metrics:

Metrics
=======

New in buildbot 0.8.4 is support for tracking various performance metrics inside the buildbot master process.
Currently these are logged periodically according to the ``log_interval`` configuration setting of the :bb:cfg:`metrics` configuration.

The metrics subsystem is implemented in :mod:`buildbot.process.metrics`.
It makes use of twisted's logging system to pass metrics data from all over buildbot's code to a central :class:`MetricsLogObserver` object, which is available at ``BuildMaster.metrics`` or via ``Status.getMetrics()``.

Metric Events
-------------

:class:`MetricEvent` objects represent individual items to monitor.
There are three sub-classes implemented:

:class:`MetricCountEvent`
    Records incremental increase or decrease of some value, or an absolute measure of some value.

    ::

        from buildbot.process.metrics import MetricCountEvent

        # We got a new widget!
        MetricCountEvent.log('num_widgets', 1)

        # We have exactly 10 widgets
        MetricCountEvent.log('num_widgets', 10, absolute=True)

:class:`MetricTimeEvent`
    Measures how long things take. By default the average of the last 10 times will be reported.

    ::

        from buildbot.process.metrics import MetricTimeEvent

        # function took 0.001s
        MetricTimeEvent.log('time_function', 0.001)

:class:`MetricAlarmEvent`
    Indicates the health of various metrics.

    ::

        from buildbot.process.metrics import MetricAlarmEvent, ALARM_OK

        # num_workers looks ok
        MetricAlarmEvent.log('num_workers', level=ALARM_OK)

Metric Handlers
---------------

:class:`MetricsHandler` objects are responsible for collecting :class:`MetricEvent`\s of a specific type and keeping track of their values for future reporting.
There are :class:`MetricsHandler` classes corresponding to each of the :class:`MetricEvent` types.

Metric Watchers
---------------

Watcher objects can be added to :class:`MetricsHandlers` to be called when metric events of a certain type are received.
Watchers are generally used to record alarm events in response to count or time events.

Metric Helpers
--------------

:func:`countMethod(name)`
    A function decorator that counts how many times the function is called.

    ::

        from buildbot.process.metrics import countMethod

        @countMethod('foo_called')
        def foo():
            return "foo!"

:func:`Timer(name)`
    :class:`Timer` objects can be used to make timing events easier.
    When ``Timer.stop()`` is called, a :class:`MetricTimeEvent` is logged with the elapsed time since ``timer.start()`` was called.

    ::

        from buildbot.process.metrics import Timer

        def foo():
            t = Timer('time_foo')
            t.start()
            try:
                for i in range(1000):
                    calc(i)
                return "foo!"
            finally:
                t.stop()

    :class:`Timer` objects also provide a pair of decorators, :func:`startTimer`/\ :func:`stopTimer` to decorate other functions.

    ::

        from buildbot.process.metrics import Timer

        t = Timer('time_thing')

        @t.startTimer
        def foo():
            return "foo!"

        @t.stopTimer
        def bar():
            return "bar!"

        foo()
        bar()

:func:`timeMethod(name)`
    A function decorator that measures how long a function takes to execute.
    Note that many functions in buildbot return deferreds, so may return before all the work they set up has completed.
    Using an explicit :class:`Timer` is better in this case.

    ::

        from buildbot.process.metrics import timeMethod

        @timeMethod('time_foo')
        def foo():
            for i in range(1000):
                calc(i)
            return "foo!"
