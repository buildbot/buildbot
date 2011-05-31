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

"""
A complete re-implementation of the database connector components, but without
using a database.  These classes should pass the same tests as are applied to
the real connector components.
"""

import base64
from buildbot.util import json, epoch2datetime
from twisted.python import failure
from twisted.internet import defer, reactor
from buildbot.db import buildrequests
from buildbot.process import properties

# Fake DB Rows

class Row(object):
    """
    Parent class for row classes, which are used to specify test data for
    database-related tests.

    @cvar defaults: default values for columns
    @type defaults: dictionary

    @cvar table: the table name

    @cvar id_column: specify a column that should be assigned an
    auto-incremented id.  Auto-assigned id's begin at 1000, so any explicitly
    specified ID's should be less than 1000.

    @cvar id_column: a tuple of columns that must be given in the constructor

    @ivar values: the values to be inserted into this row
    """

    id_column = ()
    required_columns = ()

    def __init__(self, **kwargs):
        self.values = self.defaults.copy()
        self.values.update(kwargs)
        if self.id_column:
            if self.values[self.id_column] is None:
                self.values[self.id_column] = self.nextId()
        for col in self.required_columns:
            assert col in kwargs, "%s not specified" % col
        # make the values appear as attributes
        self.__dict__.update(self.values)

    def nextId(self):
        if not hasattr(self.__class__, '_next_id'):
            self.__class__._next_id = 1000
        else:
            self.__class__._next_id += 1
        return self.__class__._next_id


class BuildRequest(Row):
    table = "buildrequests"

    defaults = dict(
        id = None,
        buildsetid = None,
        buildername = "bldr",
        priority = 0,
        claimed_at = 0,
        claimed_by_name = None,
        claimed_by_incarnation = None,
        complete = 0,
        results = -1,
        submitted_at = 0,
        complete_at = 0,
    )

    id_column = 'id'
    required_columns = ('buildsetid',)


class Change(Row):
    table = "changes"

    defaults = dict(
        changeid = None,
        author = 'frank',
        comments = 'test change',
        is_dir = 0,
        branch = 'master',
        revision = 'abcd',
        revlink = 'http://vc/abcd',
        when_timestamp = 1200000,
        category = 'cat',
        repository = 'repo',
        project = 'proj',
    )

    id_column = 'changeid'


class ChangeFile(Row):
    table = "change_files"

    defaults = dict(
        changeid = None,
        filename = None,
    )

    required_columns = ('changeid',)


class ChangeLink(Row):
    table = "change_links"

    defaults = dict(
        changeid = None,
        link = None,
    )

    required_columns = ('changeid',)


class ChangeProperty(Row):
    table = "change_properties"

    defaults = dict(
        changeid = None,
        property_name = None,
        property_value = None,
    )

    required_columns = ('changeid',)


class Patch(Row):
    table = "patches"

    defaults = dict(
        id = None,
        patchlevel = 0,
        patch_base64 = 'aGVsbG8sIHdvcmxk', # 'hello, world'
        subdir = None,
    )

    id_column = 'id'


class SourceStampChange(Row):
    table = "sourcestamp_changes"

    defaults = dict(
        sourcestampid = None,
        changeid = None,
    )

    required_columns = ('sourcestampid', 'changeid')


class SourceStamp(Row):
    table = "sourcestamps"

    defaults = dict(
        id = None,
        branch = 'master',
        revision = 'abcd',
        patchid = None,
        repository = 'repo',
        project = 'proj',
    )

    id_column = 'id'


class Scheduler(Row):
    table = "schedulers"

    defaults = dict(
        schedulerid = None,
        name = 'testsched',
        state = '{}',
        class_name = 'TestScheduler',
    )

    id_column = 'schedulerid'


class SchedulerChange(Row):
    table = "scheduler_changes"

    defaults = dict(
        schedulerid = None,
        changeid = None,
        important = 1,
    )

    required_columns = ( 'schedulerid', 'changeid' )


class Buildset(Row):
    table = "buildsets"

    defaults = dict(
        id = None,
        external_idstring = 'extid',
        reason = 'because',
        sourcestampid = None,
        submitted_at = 12345678,
        complete = 0,
        complete_at = None,
        results = -1,
    )

    id_column = 'id'
    required_columns = ( 'sourcestampid', )


class BuildsetProperty(Row):
    table = "buildset_properties"

    defaults = dict(
        buildsetid = None,
        property_name = 'prop',
        property_value = '[22, "fakedb"]',
    )

    required_columns = ( 'buildsetid', )


class SchedulerUpstreamBuildset(Row):
    table = "scheduler_upstream_buildsets"

    defaults = dict(
        buildsetid = None,
        schedulerid = None,
        active = 0,
    )

    required_columns = ( 'buildsetid', 'schedulerid' )


class Object(Row):
    table = "objects"

    defaults = dict(
        id = None,
        name = 'nam',
        class_name = 'cls',
    )

    id_column = 'id'


class ObjectState(Row):
    table = "object_state"

    defaults = dict(
        objectid = None,
        name = 'nam',
        value_json = '{}',
    )

    required_columns = ( 'objectid', )

class Build(Row):
    table = "builds"

    defaults = dict(
        id = None,
        number = 29,
        brid = 39,
        start_time = 1304262222,
        finish_time = None)

    id_column = 'id'

# Fake DB Components

# TODO: test these using the same test methods as are used against the real
# database

class FakeDBComponent(object):

    def __init__(self, db, testcase):
        self.db = db
        self.t = testcase
        self.setUp()


class FakeChangesComponent(FakeDBComponent):

    def setUp(self):
        self.changes = {}

    class ChangeInstance(object): pass
    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Change):
                ch = self.ChangeInstance()
                ch.__dict__.update(dict(
                    # TODO: this renaming sucks.
                    number=row.changeid, who=row.author, files=[],
                    comments=row.comments, isdir=row.is_dir, links=[],
                    revision=row.revision, when=row.when_timestamp,
                    branch=row.branch, category=row.category,
                    revlink=row.revlink, properties=properties.Properties(),
                    repository=row.repository, project=row.project))
                self.changes[row.changeid] = ch

            elif isinstance(row, ChangeFile):
                ch = self.changes[row.changeid]
                ch.files.append(row.filename)

            elif isinstance(row, ChangeLink):
                ch = self.changes[row.changeid]
                ch.links.append(row.link)

            elif isinstance(row, ChangeProperty):
                ch = self.changes[row.changeid]
                n, vs = row.property_name, row.property_value
                v, s = json.loads(vs)
                ch.properties.setProperty(n, v, s)

    # component methods

    def getLatestChangeid(self):
        if self.changes:
            return defer.succeed(max(self.changes.iterkeys()))
        return defer.succeed(None)

    def getChange(self, changeid):
        try:
            ch = self.changes[changeid]
        except KeyError:
            ch = None
        return defer.succeed(self._ch2chdict(ch))

    # TODO: addChange
    # TODO: getRecentChanges

    # utilities

    def _ch2chdict(self, ch):
        if not ch:
            return None
        return dict(
            changeid=ch.number,
            author=ch.who,
            comments=ch.comments,
            is_dir=ch.isdir,
            links=ch.links,
            revision=ch.revision,
            branch=ch.branch,
            category=ch.category,
            revlink=ch.revlink,
            repository=ch.repository,
            project=ch.project,
            files=ch.files,
            when_timestamp=epoch2datetime(ch.when),
            properties=dict([ (k,(v,s))
                for k,v,s in ch.properties.asDict() ]),
        )
    # fake methods

    def fakeAddChange(self, change):
        if not hasattr(change, 'number') or not change.number:
            if self.changes:
                change.number = max(self.changes.iterkeys()) + 1
            change.number = 500
        self.changes[change.number] = change


class FakeSchedulersComponent(FakeDBComponent):

    def setUp(self):
        self.states = {}
        self.classifications = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Scheduler):
                self.states[row.schedulerid] = json.loads(row.state)

            elif isinstance(row, SchedulerChange):
                cls = self.classifications.setdefault(row.schedulerid, {})
                cls[row.changeid] = row.important

    # component methods

    def getState(self, schedulerid):
        return defer.succeed(self.states.get(schedulerid, {}))

    def setState(self, schedulerid, state):
        self.states[schedulerid] = state
        return defer.succeed(None)

    def classifyChanges(self, schedulerid, classifications):
        self.classifications.setdefault(schedulerid, {}).update(classifications)
        return defer.succeed(None)

    def flushChangeClassifications(self, schedulerid, less_than=None):
        if less_than is not None:
            classifications = self.classifications.setdefault(schedulerid, {})
            for changeid in classifications.keys():
                if changeid < less_than:
                    del classifications[changeid]
        else:
            self.classifications[schedulerid] = {}
        return defer.succeed(None)

    def getChangeClassifications(self, schedulerid, branch=-1):
        classifications = self.classifications.setdefault(schedulerid, {})
        if branch is not -1:
            # filter out the classifications for the requested branch
            change_branches = dict(
                    (id, getattr(c, 'branch', None))
                    for id, c in self.db.changes.changes.iteritems() )
            classifications = dict(
                    (k,v) for (k,v) in classifications.iteritems()
                    if k in change_branches and change_branches[k] == branch )
        return defer.succeed(classifications)

    # fake methods

    def fakeState(self, schedulerid, state):
        """Set the state dictionary for a scheduler"""
        self.states[schedulerid] = state

    def fakeClassifications(self, schedulerid, classifications):
        """Set the set of classifications for a scheduler"""
        self.classifications[schedulerid] = classifications

    # assertions

    def assertState(self, schedulerid, state):
        self.t.assertEqual(self.states[schedulerid], state)

    def assertClassifications(self, schedulerid, classifications):
        self.t.assertEqual(
                self.classifications.get(schedulerid, {}),
                classifications)


class FakeSourceStampsComponent(FakeDBComponent):

    def setUp(self):
        self.sourcestamps = {}
        self.patches = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Patch):
                self.patches[row.id] = dict(
                    patch_level=row.patchlevel,
                    patch_body=base64.b64decode(row.patch_base64),
                    patch_subdir=row.subdir)

        for row in rows:
            if isinstance(row, SourceStamp):
                ss = self.sourcestamps[row.id] = row.values.copy()
                ss['changeids'] = set()

        for row in rows:
            if isinstance(row, SourceStampChange):
                ss = self.sourcestamps[row.sourcestampid]
                ss['changeids'].add(row.changeid)

    # component methods

    def addSourceStamp(self, branch, revision, repository, project,
                          patch_body=None, patch_level=0, patch_subdir=None,
                          changeids=[]):
        id = len(self.sourcestamps) + 100
        while id in self.sourcestamps:
            id += 1

        changeids = set(changeids)

        if patch_body:
            patchid = len(self.patches) + 100
            while patchid in self.patches:
                patchid += 1
            self.patches[patchid] = dict(
                patch_level=patch_level,
                patch_body=patch_body,
                patch_subdir=patch_subdir,
            )
        else:
            patchid = None

        self.sourcestamps[id] = dict(id=id, branch=branch, revision=revision,
                patchid=patchid, repository=repository, project=project,
                changeids=changeids)
        return defer.succeed(id)

    def getSourceStamp(self, ssid):
        if ssid in self.sourcestamps:
            ssdict = self.sourcestamps[ssid].copy()
            del ssdict['id']
            ssdict['ssid'] = ssid
            patchid = ssdict['patchid']
            if patchid:
                ssdict.update(self.patches[patchid])
            else:
                ssdict['patch_body'] = None
                ssdict['patch_level'] = None
                ssdict['patch_subdir'] = None
            del ssdict['patchid']
            return defer.succeed(ssdict)
        else:
            return defer.succeed(None)


class FakeBuildsetsComponent(FakeDBComponent):

    def setUp(self):
        self.buildsets = {}
        self.completed_bsids = set()
        self.buildset_subs = []

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Buildset):
                bs = self.buildsets[row.id] = row.values.copy()
                bs['properties'] = {}
            if isinstance(row, SchedulerUpstreamBuildset):
                self.buildset_subs.append((row.schedulerid, row.buildsetid))

        for row in rows:
            if isinstance(row, BuildsetProperty):
                assert row.buildsetid in self.buildsets
                n = row.property_name
                v, src = tuple(json.loads(row.property_value))
                self.buildsets[row.buildsetid]['properties'][n] = (v, src)

    # component methods

    def _newBsid(self):
        bsid = 200
        while bsid in self.buildsets:
            bsid += 1
        return bsid

    def addBuildset(self, ssid, reason, properties, builderNames,
                   external_idstring=None, _reactor=reactor):
        bsid = self._newBsid()
        br_rows = []
        for buildername in builderNames:
            br_rows.append(
                    BuildRequest(buildsetid=bsid, buildername=buildername))
        self.db.buildrequests.insertTestData(br_rows)

        # make up a row and keep its dictionary, with the properties tacked on
        bsrow = Buildset(sourcestampid=ssid, reason=reason, external_idstring=external_idstring)
        self.buildsets[bsid] = bsrow.values.copy()
        self.buildsets[bsid]['properties'] = properties

        return defer.succeed((bsid,
            dict([ (br.buildername, br.id) for br in br_rows ])))

    def completeBuildset(self, bsid, results, _reactor=reactor):
        self.buildsets[bsid]['results'] = results
        self.buildsets[bsid]['complete'] = 1
        self.buildsets[bsid]['complete_at'] = _reactor.seconds
        return defer.succeed(None)

    def subscribeToBuildset(self, schedulerid, buildsetid):
        self.buildset_subs.append((schedulerid, buildsetid))
        return defer.succeed(None)

    def unsubscribeFromBuildset(self, schedulerid, buildsetid):
        self.buildset_subs.remove((schedulerid, buildsetid))
        return defer.succeed(None)

    def getSubscribedBuildsets(self, schedulerid):
        bsids = [ b for (s, b) in self.buildset_subs if s == schedulerid ]
        rv = [ (bsid,
                self.buildsets[bsid]['sourcestampid'],
                bsid in self.completed_bsids,
                self.buildsets[bsid].get('results', -1))
                for bsid in bsids ]
        return defer.succeed(rv)

    def getBuildset(self, bsid):
        if bsid not in self.buildsets:
            return defer.succeed(None)
        row = self.buildsets[bsid]
        return defer.succeed(self._row2dict(row))

    def getBuildsets(self, complete=None):
        rv = []
        for bs in self.buildsets.itervalues():
            if complete is not None:
                if complete and bs['complete']:
                    rv.append(self._row2dict(bs))
                elif not complete and not bs['complete']:
                    rv.append(self._row2dict(bs))
            else:
                rv.append(self._row2dict(bs))
        return defer.succeed(rv)

    def _row2dict(self, row):
        row = row.copy()
        if row['complete_at']:
            row['complete_at'] = epoch2datetime(row['complete_at'])
        else:
            row['complete_at'] = None
        row['submitted_at'] = row['submitted_at'] and \
                             epoch2datetime(row['submitted_at'])
        row['complete'] = bool(row['complete'])
        row['bsid'] = row['id']
        del row['id']
        return row

    def getBuildsetProperties(self, buildsetid):
        if buildsetid in self.buildsets:
            return defer.succeed(
                    self.buildsets[buildsetid]['properties'])
        else:
            return defer.succeed({})

    # fake methods

    def fakeBuildsetCompletion(self, bsid, result):
        assert bsid in self.buildsets
        self.buildsets[bsid]['results'] = result
        self.completed_bsids.add(bsid)

    def flushBuildsets(self):
        """
        Flush the set of buildsets, for example after C{assertBuildset}
        """
        self.buildsets = {}
        self.completed_bsids = set()

    # assertions

    def assertBuildsets(self, count):
        """Assert that exactly COUNT buildsets were added"""
        self.t.assertEqual(len(self.buildsets), count,
                    "buildsets are %r" % (self.buildsets,))

    def assertBuildset(self, bsid, expected_buildset, expected_sourcestamp):
        """Assert that the buildset and its attached sourcestamp look as
        expected; the ssid parameter of the buildset is omitted.  Properties
        are converted with asList and sorted.  Sourcestamp patches are inlined
        (patch_body, patch_level, patch_subdir), and changeids are represented
        as a set, but omitted if empty.  If bsid is '?', then assert there is
        only one new buildset, and use that."""
        if bsid == '?':
            self.assertBuildsets(1)
            bsid = self.buildsets.keys()[0]
        else:
            self.t.assertIn(bsid, self.buildsets)

        buildset = self.buildsets[bsid].copy()
        ss = self.db.sourcestamps.sourcestamps[buildset['sourcestampid']].copy()
        del buildset['sourcestampid']

        if 'id' in buildset:
            del buildset['id']

        # clear out some columns if the caller doesn't care
        for col in 'complete complete_at submitted_at results'.split():
            if col not in expected_buildset:
                del buildset[col]

        if buildset['properties']:
            buildset['properties'] = sorted(buildset['properties'].items())

        # only add brids if we're expecting them (sometimes they're unknown)
        if 'brids' in expected_buildset:
            brids = dict([ (br.buildername, br.id)
                      for br in self.db.buildrequests.reqs.values()
                      if br.buildsetid == bsid ])
            buildset['brids'] = brids

        if 'id' in ss:
            del ss['id']
        if not ss['changeids']:
            del ss['changeids']

        # incorporate patch info if we have it
        if 'patchid' in ss and ss['patchid']:
            ss.update(self.db.sourcestamps.patches[ss['patchid']])
        del ss['patchid']

        self.t.assertEqual(
            dict(buildset=buildset, sourcestamp=ss),
            dict(buildset=expected_buildset, sourcestamp=expected_sourcestamp))
        return bsid

    def allBuildsetIds(self):
        return self.buildsets.keys()

    def assertBuildsetSubscriptions(self, *subscriptions):
        self.t.assertEqual(sorted(subscriptions),
                         sorted(self.buildset_subs))


class FakeStateComponent(FakeDBComponent):

    def setUp(self):
        self.objects = {}
        self.states = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Object):
                self.objects[(row.name, row.class_name)] = row.id
                self.states[row.id] = {}

        for row in rows:
            if isinstance(row, ObjectState):
                assert row.objectid in self.objects.values()
                self.states[row.objectid][row.name] = row.value_json

    # component methods

    def _newId(self):
        id = 100
        while id in self.states:
            id += 1
        return id

    def getObjectId(self, name, class_name):
        try:
            id = self.objects[(name, class_name)]
        except:
            # invent a new id and add it
            id = self.objects[(name, class_name)] = self._newId()
            self.states[id] = {}
        return defer.succeed(id)

    def getState(self, objectid, name, default=object):
        try:
            json_value = self.states[objectid][name]
        except KeyError:
            if default is not object:
                return default
            raise
        return defer.succeed(json.loads(json_value))

    def setState(self, objectid, name, value):
        self.states[objectid][name] = json.dumps(value)
        return defer.succeed(None)

    # fake methods

    def fakeState(self, name, class_name, **kwargs):
        id = self.objects[(name, class_name)] = self._newId()
        self.objects[(name, class_name)] = id
        self.states[id] = dict( (k, json.dumps(v))
                                for k,v in kwargs.iteritems() )
        return id

    # assertions

    def assertState(self, objectid, **kwargs):
        state = self.states[objectid]
        for k,v in kwargs.iteritems():
            self.t.assertIn(k, state)
            self.t.assertEqual(json.loads(state[k]), v,
                    "state is %r" % (state,))


class FakeBuildRequestsComponent(FakeDBComponent):

    # for use in determining "my" requests
    MASTER_NAME = "this-master"
    MASTER_INCARNATION = "this-lifetime"

    # override this to set reactor.seconds
    _reactor = reactor

    def setUp(self):
        self.reqs = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, BuildRequest):
                self.reqs[row.id] = row

    # component methods

    def getBuildRequest(self, brid):
        try:
            return defer.succeed(self._brdictFromRow(self.reqs[brid]))
        except:
            return defer.succeed(None)

    def getBuildRequests(self, buildername=None, complete=None, claimed=None,
                         bsid=None):
        rv = []
        for br in self.reqs.itervalues():
            if buildername and br.buildername != buildername:
                continue
            if complete is not None:
                if complete and not br.complete:
                    continue
                if not complete and br.complete:
                    continue
            if claimed is not None:
                if claimed == "mine":
                    if br.claimed_by_name != self.MASTER_NAME:
                        continue
                    if br.claimed_by_incarnation != self.MASTER_INCARNATION:
                        continue
                elif claimed:
                    if not br.claimed_at:
                        continue
                else:
                    if br.claimed_at:
                        continue
            if bsid is not None:
                if br.buildsetid != bsid:
                    continue
            rv.append(self._brdictFromRow(br))
        return defer.succeed(rv)

    def claimBuildRequests(self, brids):
        for brid in brids:
            if brid not in self.reqs:
                return defer.fail(
                        failure.Failure(buildrequests.AlreadyClaimedError))
            br = self.reqs[brid]
            if br.claimed_at and (
                    br.claimed_by_name != self.MASTER_NAME or
                    br.claimed_by_incarnation != self.MASTER_INCARNATION):
                return defer.fail(
                        failure.Failure(buildrequests.AlreadyClaimedError))
        # now that we've thrown any necessary exceptions, get started
        for brid in brids:
            br = self.reqs[brid]
            br.claimed_at = self._reactor.seconds()
            br.claimed_by_name = self.MASTER_NAME
            br.claimed_by_incarnation = self.MASTER_INCARNATION
        return defer.succeed(None)

    def unclaimOldIncarnationRequests(self):
        for br in self.reqs.itervalues():
            if (not br.complete and br.claimed_at and
                    br.claimed_by_name == self.MASTER_NAME and
                    br.claimed_by_incarnation != self.MASTER_INCARNATION):
                br.claimed_at = 0
                br.claimed_by_name = None
                br.claimed_by_incarnation = None
        return defer.succeed(None)

    def unclaimExpiredRequests(self, old):
        old_time = self._reactor.seconds() - old
        for br in self.reqs.itervalues():
            if not br.complete and br.claimed_at and br.claimed_at < old_time:
                br.claimed_at = 0
                br.claimed_by_name = None
                br.claimed_by_incarnation = None
        return defer.succeed(None)

    # Code copied from buildrequests.BuildRequestConnectorComponent
    def _brdictFromRow(self, row):
        claimed = mine = False
        if (row.claimed_at
                and row.claimed_by_name is not None
                and row.claimed_by_incarnation is not None):
            claimed = True
            master_name = self.db.master.master_name
            master_incarnation = self.db.master.master_incarnation
            if (row.claimed_by_name == master_name and
                row.claimed_by_incarnation == master_incarnation):
               mine = True

        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
        submitted_at = mkdt(row.submitted_at)
        claimed_at = mkdt(row.claimed_at)
        complete_at = mkdt(row.complete_at)

        return dict(brid=row.id, buildsetid=row.buildsetid,
                buildername=row.buildername, priority=row.priority,
                claimed=claimed, claimed_at=claimed_at, mine=mine,
                complete=bool(row.complete), results=row.results,
                submitted_at=submitted_at, complete_at=complete_at)

    # fake methods

    def fakeClaimBuildRequest(self, brid, claimed_at=None, master_name=None,
                                          master_incarnation=None):
        br = self.reqs[brid]
        br.claimed_at = claimed_at or self._reactor.seconds()
        br.claimed_by_name = master_name or self.MASTER_NAME
        br.claimed_by_incarnation = \
                master_incarnation or self.MASTER_INCARNATION

    def fakeUnclaimBuildRequest(self, brid):
        br = self.reqs[brid]
        br.claimed_at = 0
        br.claimed_by_name = None
        br.claimed_by_incarnation = None

    # assertions

    def assertClaimed(self, brid, master_name=None, master_incarnation=None):
        self.t.assertTrue(self.reqs[brid].claimed_at)
        if master_name and master_incarnation:
            br = self.reqs[brid]
            self.t.assertEqual(
                [ br.claimed_by_name, br.claimed_by_incarnation ]
                [ master_name, master_incarnation ])

    def assertClaimedMine(self, brid):
        return self.t.assertClaimed(brid, master_name=self.MASTER_NAME,
                master_incarnation=self.MASTER_INCARNATION)

    def assertMyClaims(self, claimed_brids):
        self.t.assertEqual(
                [ id for (id, br) in self.reqs.iteritems()
                  if br.claimed_by_name == self.MASTER_NAME and
                     br.claimed_by_incarnation == self.MASTER_INCARNATION ],
                claimed_brids)


class FakeBuildsComponent(FakeDBComponent):

    def setUp(self):
        self.builds = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Build):
                self.builds[row.id] = row

    # component methods

    def _newId(self):
        id = 100
        while id in self.builds:
            id += 1
        return id

    def getBuild(self, bid):
        row = self.builds.get(bid)
        if not row:
            return defer.succeed(None)

        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
        return defer.succeed(dict(
            bid=row.id,
            brid=row.brid,
            number=row.number,
            start_time=mkdt(row.start_time),
            finish_time=mkdt(row.finish_time)))
    
    def getBuildsForRequest(self, brid):
        ret = []
        def mkdt(epoch):
            if epoch:
                return epoch2datetime(epoch)
 
        for (id, row) in self.builds.items():
            if row.brid == brid:
                ret.append(dict(bid = row.id,
                                brid=row.brid,
                                number=row.number,
                                start_time=mkdt(row.start_time),
                                finish_time=mkdt(row.finish_time)))
               
        return defer.succeed(ret)            

    def addBuild(self, brid, number, _reactor=reactor):
        bid = self._newId()
        self.builds[bid] = Build(id=bid, number=number, brid=brid,
                start_time=_reactor.seconds, finish_time=None)
        return bid

    def finishBuilds(self, bids, _reactor=reactor):
        now = _reactor.seconds()
        for bid in bids:
            b = self.builds.get(bid)
            if b:
                b.finish_time = now


class FakeDBConnector(object):
    """
    A stand-in for C{master.db} that operates without an actual database
    backend.  This also implements a test-data interface similar to the
    L{buildbot.test.util.db.RealDatabaseMixin.insertTestData} method.

    The child classes implement various useful assertions and faking methods;
    see their documentation for more.
    """

    def __init__(self, testcase):
        self._components = []
        self.changes = comp = FakeChangesComponent(self, testcase)
        self._components.append(comp)
        self.schedulers = comp = FakeSchedulersComponent(self, testcase)
        self._components.append(comp)
        self.sourcestamps = comp = FakeSourceStampsComponent(self, testcase)
        self._components.append(comp)
        self.buildsets = comp = FakeBuildsetsComponent(self, testcase)
        self._components.append(comp)
        self.state = comp = FakeStateComponent(self, testcase)
        self._components.append(comp)
        self.buildrequests = comp = FakeBuildRequestsComponent(self, testcase)
        self._components.append(comp)
        self.builds = comp = FakeBuildsComponent(self, testcase)
        self._components.append(comp)

    def insertTestData(self, rows):
        """Insert a list of Row instances into the database; this method can be
        called synchronously or asynchronously (it completes immediately) """
        for comp in self._components:
            comp.insertTestData(rows)
        return defer.succeed(None)
