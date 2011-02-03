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

from twisted.internet import defer
from buildbot.util import json

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
                    revlink=row.revlink, properties={},
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
                n, v = row.property_name, row.property_value
                ch.properties[n] = json.loads(v)

    # component methods

    def getLatestChangeid(self):
        if self.changes:
            return defer.succeed(max(self.changes.iterkeys()))
        return defer.succeed(None)

    def getChangeInstance(self, changeid):
        try:
            return defer.succeed(self.changes[changeid])
        except KeyError:
            return defer.succeed(None)

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

    class Thunk: pass
    def getChangeClassifications(self, schedulerid, branch=Thunk):
        classifications = self.classifications.setdefault(schedulerid, {})
        if branch is not self.Thunk:
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

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, SourceStamp):
                self.sourcestamps[row.id] = row.values.copy()

    # component methods

    def _sync_create(self, **kwargs):
        id = len(self.sourcestamps) + 100
        while id in self.sourcestamps:
            id += 1
        kwargs['id'] = id
        self.sourcestamps[id] = kwargs
        return id

    def createSourceStamp(self, **kwargs):
        return defer.succeed(self._sync_create(**kwargs))

    # fake methods

    def fakeSourceStamp(self, **kwargs):
        """Add a sourcestamp, returning the ssid"""
        return self._sync_create(**kwargs)


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
                self.buildsets[row.id]['properties'][n] = (v, src)

    # component methods

    def _newBsid(self):
        bsid = 200
        while bsid in self.buildsets:
            bsid += 1
        return bsid

    def addBuildset(self, **kwargs):
        bsid = kwargs['id'] = self._newBsid()
        self.buildsets[bsid] = kwargs
        return defer.succeed(bsid)

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
        are converted with asList and sorted.  If bsid is '?', then assert
        there is only one new buildset, and use that"""
        if bsid == '?':
            self.assertBuildsets(1)
            bsid = self.buildsets.keys()[0]
        else:
            self.t.assertIn(bsid, self.buildsets)

        buildset = self.buildsets[bsid].copy()
        ss = self.db.sourcestamps.sourcestamps[buildset['ssid']].copy()
        del buildset['ssid']

        if 'id' in buildset:
            del buildset['id']

        if 'id' in ss:
            del ss['id']

        if buildset['properties']:
            buildset['properties'] = sorted(buildset['properties'].items())

        if 'changeids' in ss:
            ss['changeids'].sort()

        if 'patchid' in ss and not ss['patchid']:
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

    def insertTestData(self, rows):
        """Insert a list of Row instances into the database; this method can be
        called synchronously or asynchronously (it completes immediately) """
        for comp in self._components:
            comp.insertTestData(rows)
        return defer.succeed(None)
