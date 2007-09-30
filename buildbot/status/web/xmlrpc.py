
from twisted.python import log
from twisted.web import xmlrpc
from buildbot.status.builder import Results
from itertools import count

class XMLRPCServer(xmlrpc.XMLRPC):
    def __init__(self):
        xmlrpc.XMLRPC.__init__(self)

    def render(self, req):
        # extract the IStatus and IControl objects for later use, since they
        # come from the request object. They'll be the same each time, but
        # they aren't available until the first request arrives.
        self.status = req.site.buildbot_service.getStatus()
        self.control = req.site.buildbot_service.getControl()
        return xmlrpc.XMLRPC.render(self, req)

    def xmlrpc_getAllBuildsInInterval(self, start, stop):
        """Return a list of builds that have completed after the 'start'
        timestamp and before the 'stop' timestamp. This looks at all
        Builders.

        The timestamps are integers, interpreted as standard unix timestamps
        (seconds since epoch).

        Each Build is returned as a tuple in the form::
         (buildername, buildnumber, build_end, branchname, revision,
          results, text)

        The buildnumber is an integer. 'build_end' is an integer (seconds
        since epoch) specifying when the build finished.

        The branchname is a string, which may be an empty string to indicate
        None (i.e. the default branch). The revision is a string whose
        meaning is specific to the VC system in use, and comes from the
        'got_revision' build property. The results are expressed as a string,
        one of ('success', 'warnings', 'failure', 'exception'). The text is a
        list of short strings that ought to be joined by spaces and include
        slightly more data about the results of the build.
        """
        #log.msg("start: %s %s %s" % (start, type(start), start.__class__))
        log.msg("getAllBuildsInInterval: %d - %d" % (start, stop))
        all_builds = []

        for builder_name in self.status.getBuilderNames():
            builder = self.status.getBuilder(builder_name)
            for build_number in count(1):
                build = builder.getBuild(-build_number)
                if not build:
                    break
                if not build.isFinished():
                    continue
                (build_start, build_end) = build.getTimes()
                # in reality, builds are mostly ordered by start time. For
                # the purposes of this method, we pretend that they are
                # strictly ordered by end time, so that we can stop searching
                # when we start seeing builds that are outside the window.
                if build_end > stop:
                    continue # keep looking
                if build_end < start:
                    break # stop looking

                ss = build.getSourceStamp()
                branch = ss.branch
                if branch is None:
                    branch = ""
                try:
                    revision = build.getProperty("got_revision")
                except KeyError:
                    revision = ""
                revision = str(revision)

                answer = (builder_name,
                          build.getNumber(),
                          build_end,
                          branch,
                          revision,
                          Results[build.getResults()],
                          build.getText(),
                          )
                all_builds.append((build_end, answer))
            # we've gotten all the builds that we care about from this
            # particular builder, so now we can continue on the next builder

        # now we've gotten all the builds we're interested in. Sort them by
        # end time.
        all_builds.sort(lambda a,b: cmp(a[0], b[0]))
        # and remove the timestamps
        all_builds = [t[1] for t in all_builds]

        log.msg("ready to go: %s" % (all_builds,))

        return all_builds

    def xmlrpc_getBuild(self, builder_name, build_number):
        """Return information about a specific build.

        """
        builder = self.status.getBuilder(builder_name)
        build = builder.getBuild(build_number)
        info = {}
        info['builder_name'] = builder.getName()
        info['url'] = self.status.getURLForThing(build)
        info['reason'] = build.getReason()
        info['slavename'] = build.getSlavename()
        info['results'] = build.getResults()
        info['text'] = build.getText()
        ss = build.getSourceStamp()
        info['start'], info['end'] = build.getTimes()

        info_steps = []
        for s in build.getSteps():
            stepinfo = {}
            stepinfo['name'] = s.getName()
            stepinfo['start'], stepinfo['end'] = s.getTimes()
            stepinfo['results'] = s.getResults()
            info_steps.append(stepinfo)
        info['steps'] = info_steps

        info_logs = []
        for l in build.getLogs():
            loginfo = {}
            loginfo['name'] = l.getStep().getName() + "/" + l.getName()
            #loginfo['text'] = l.getText()
            loginfo['text'] = "HUGE"
            info_logs.append(loginfo)
        info['logs'] = info_logs

        return info

