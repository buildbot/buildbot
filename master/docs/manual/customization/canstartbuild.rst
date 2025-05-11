.. _canStartBuild-Functions:

``canStartBuild`` Functions
---------------------------

Sometimes, you cannot know in advance what workers to assign to a :class:`BuilderConfig`. For
example, you might need to check for the existence of a file on a worker before running a build on
it. It is possible to do that by setting the ``canStartBuild`` callback.

Here is an example that checks if there is a ``vm`` property set for the build request. If it is
set, it checks if a file named after it exists in the ``/opt/vm`` folder. If the file does not
exist on the given worker, refuse to run the build to force the master to select another worker.

.. code-block:: python

   @defer.inlineCallbacks
   def canStartBuild(builder, wfb, request):

       vm = request.properties.get('vm', builder.config.properties.get('vm'))
       if vm:
           args = {'file': os.path.join('/opt/vm', vm)}
           cmd = RemoteCommand('stat', args, stdioLogName=None)
           cmd.worker = wfb.worker
           res = yield cmd.run(None, wfb.worker.conn, builder.name)
           if res.rc != 0:
               return False

       return True

Here is a more complete example that checks if a worker is fit to start a build. If the load
average is higher than the number of CPU cores or if there is less than 2GB of free memory, refuse
to run the build on that worker. Also, put that worker in quarantine to make sure no other builds
are scheduled on it for a while. Otherwise, let the build start on that worker.

.. code-block:: python

   class FakeBuild(object):
       properties = Properties()

   class FakeStep(object):
       build = FakeBuild()

   @defer.inlineCallbacks
   def shell(command, worker, builder):
       args = {
           'command': command,
           'logEnviron': False,
           'workdir': worker.worker_basedir,
           'want_stdout': False,
           'want_stderr': False,
       }
       cmd = RemoteCommand('shell', args, stdioLogName=None)
       cmd.worker = worker
       yield cmd.run(FakeStep(), worker.conn, builder.name)
       return cmd.rc

   @defer.inlineCallbacks
   def canStartBuild(builder, wfb, request):
       # check that load is not too high
       rc = yield shell(
           'test "$(cut -d. -f1 /proc/loadavg)" -le "$(nproc)"',
           wfb.worker, builder)
       if rc != 0:
           log.msg('loadavg is too high to take new builds',
                   system=repr(wfb.worker))
           wfb.worker.putInQuarantine()
           return False

       # check there is enough free memory
       sed_expr = r's/^MemAvailable:[[:space:]]+([0-9]+)[[:space:]]+kB$/\1/p'
       rc = yield shell(
           'test "$(sed -nre \'%s\' /proc/meminfo)" -gt 2000000' % sed_expr,
           wfb.worker, builder)
       if rc != 0:
           log.msg('not enough free memory to take new builds',
                   system=repr(wfb.worker))
           wfb.worker.putInQuarantine()
           return False

       # The build may now proceed.
       #
       # Prevent this worker from taking any other build while this one is
       # starting for 2 min. This leaves time for the build to start consuming
       # resources (disk, memory, cpu). When the quarantine is over, if the
       # same worker is subject to start another build, the above checks will
       # better reflect the actual state of the worker.
       wfb.worker.quarantine_timeout = 120
       wfb.worker.putInQuarantine()

       # This does not take the worker out of quarantine, it only resets the
       # timeout value to default.
       wfb.worker.resetQuarantine()

       return True

You can extend these examples using any remote command described in the :doc:`../../developer/master-worker`.
