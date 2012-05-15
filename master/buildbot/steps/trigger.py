# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, FAILURE, EXCEPTION
from buildbot.process.properties import Properties
from buildbot.schedulers.triggerable import Triggerable
from twisted.python import log
from twisted.internet import defer
from buildbot import config

class Trigger(LoggingBuildStep):
    name = "trigger"

    renderables = [ 'set_properties', 'schedulerNames', 'sourceStamps',
                    'updateSourceStamp', 'alwaysUseLatest' ]

    flunkOnFailure = True

    def __init__(self, schedulerNames=[], sourceStamp = None, sourceStamps = None,
                 updateSourceStamp=None, alwaysUseLatest=False,
                 waitForFinish=False, set_properties={}, 
                 copy_properties=[], **kwargs):
        if not schedulerNames:
            config.error(
                "You must specify a scheduler to trigger")
        if (sourceStamp or sourceStamps) and (updateSourceStamp is not None):
            config.error(
                "You can't specify both sourceStamps and updateSourceStamp")
        if (sourceStamp or sourceStamps) and alwaysUseLatest:
            config.error(
                "You can't specify both sourceStamps and alwaysUseLatest")
        if alwaysUseLatest and (updateSourceStamp is not None):
            config.error(
                "You can't specify both alwaysUseLatest and updateSourceStamp"
            )
        self.schedulerNames = schedulerNames
        self.sourceStamps = sourceStamps or []
        if sourceStamp:
            self.sourceStamps.append(sourceStamp)
        if updateSourceStamp is not None:
            self.updateSourceStamp = updateSourceStamp
        else:
            self.updateSourceStamp = not (alwaysUseLatest or self.sourceStamps)
        self.alwaysUseLatest = alwaysUseLatest
        self.waitForFinish = waitForFinish
        self.set_properties = set_properties
        self.copy_properties = copy_properties
        self.running = False
        self.ended = False
        LoggingBuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(schedulerNames=schedulerNames,
                                 sourceStamp=sourceStamp,
                                 sourceStamps=sourceStamps,
                                 updateSourceStamp=updateSourceStamp,
                                 alwaysUseLatest=alwaysUseLatest,
                                 waitForFinish=waitForFinish,
                                 set_properties=set_properties,
                                 copy_properties=copy_properties)

    def interrupt(self, reason):
        if self.running and not self.ended:
            self.step_status.setText(["interrupted"])
            return self.end(EXCEPTION)

    def end(self, result):
        if not self.ended:
            self.ended = True
            return self.finished(result)

    @defer.inlineCallbacks
    def start(self):
        properties = self.build.getProperties()

        # make a new properties object from a dict rendered by the old 
        # properties object
        props_to_set = Properties()
        props_to_set.update(self.set_properties, "Trigger")
        for p in self.copy_properties:
            if p not in properties:
                continue
            props_to_set.setProperty(p, properties[p],
                        "%s (in triggering build)" % properties.getPropertySource(p))

        self.running = True

        # (is there an easier way to find the BuildMaster?)
        all_schedulers = self.build.builder.botmaster.parent.allSchedulers()
        all_schedulers = dict([(sch.name, sch) for sch in all_schedulers])
        unknown_schedulers = []
        triggered_schedulers = []

        # don't fire any schedulers if we discover an unknown one
        for scheduler in self.schedulerNames:
            scheduler = scheduler
            if all_schedulers.has_key(scheduler):
                sch = all_schedulers[scheduler]
                if isinstance(sch, Triggerable):
                    triggered_schedulers.append(scheduler)
                else:
                    unknown_schedulers.append(scheduler)
            else:
                unknown_schedulers.append(scheduler)

        if unknown_schedulers:
            self.step_status.setText(['no scheduler:'] + unknown_schedulers)
            self.end(FAILURE)
            return

        master = self.build.builder.botmaster.parent # seriously?!
        sourceStamps = self.sourceStamps
        got = None
        if self.alwaysUseLatest:
            ss_setid = None
        else:
            ss_setid = self.build.getSourceStampSetId()
        if self.updateSourceStamp:
            got = properties.getProperty('got_revision')
            # be sure property is always a dictionary
            if got and not isinstance(got, dict):
                got = {'': got}

        dl = []
        for scheduler in triggered_schedulers:
            sch = all_schedulers[scheduler]
            dl.append(sch.trigger(ss_setid, set_props=props_to_set, 
                          got_revision=got, sourcestamps=sourceStamps))
        self.step_status.setText(['triggered'] + triggered_schedulers)

        if self.waitForFinish:
            rclist = yield defer.DeferredList(dl, consumeErrors=1)
        else:
            # do something to handle errors
            for d in dl:
                d.addErrback(log.err,
                    '(ignored) while invoking Triggerable schedulers:')
            rclist = None
            self.end(SUCCESS)
            return

        was_exception = was_failure = False
        brids = {}
        for was_cb, results in rclist:
            if isinstance(results, tuple):
                results, some_brids = results
                brids.update(some_brids)

            if not was_cb:
                was_exception = True
                log.err(results)
                continue

            if results==FAILURE:
                was_failure = True

        if was_exception:
            result = EXCEPTION
        elif was_failure:
            result = FAILURE
        else:
            result = SUCCESS

        if brids:
            def add_links(res):
                # reverse the dictionary lookup for brid to builder name
                brid_to_bn = dict((_brid,_bn) for _bn,_brid in brids.iteritems())

                for was_cb, builddicts in res:
                    if was_cb:
                        for build in builddicts:
                            bn = brid_to_bn[build['brid']]
                            num = build['number']

                            url = master.status.getURLForBuild(bn, num)
                            self.step_status.addURL("%s #%d" % (bn,num), url)

                return self.end(result)

            builddicts = [master.db.builds.getBuildsForRequest(br) for br in brids.values()]
            dl = defer.DeferredList(builddicts, consumeErrors=1)
            dl.addCallback(add_links)

        self.end(result)
        return