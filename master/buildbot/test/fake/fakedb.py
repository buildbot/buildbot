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
from buildbot.util import json, epoch2datetime, datetime2epoch
from twisted.python import failure
from twisted.internet import defer, reactor
from buildbot.db import buildrequests

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

    @cvar required_columns: a tuple of columns that must be given in the
    constructor

    @ivar values: the values to be inserted into this row
    """

    id_column = ()
    required_columns = ()
    lists = ()
    dicts = ()

    def __init__(self, **kwargs):
        self.values = self.defaults.copy()
        self.values.update(kwargs)
        if self.id_column:
            if self.values[self.id_column] is None:
                self.values[self.id_column] = self.nextId()
        for col in self.required_columns:
            assert col in kwargs, "%s not specified" % col
        for col in self.lists:
            setattr(self, col, [])
        for col in self.dicts:
            setattr(self, col, {})
        for col in kwargs.keys():
            assert col in self.defaults, "%s is not a valid column" % col
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
        complete = 0,
        results = -1,
        submitted_at = 0,
        complete_at = 0,
    )

    id_column = 'id'
    required_columns = ('buildsetid',)


class BuildRequestClaim(Row):
    table = "buildrequest_claims"

    defaults = dict(
        brid = None,
        objectid = None,
        claimed_at = None
    )

    required_columns = ('brid', 'objectid', 'claimed_at')


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
        codebase =  '',
        project = 'proj',
    )

    lists = ('files',)
    dicts = ('properties',)
    id_column = 'changeid'


class ChangeFile(Row):
    table = "change_files"

    defaults = dict(
        changeid = None,
        filename = None,
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

class ChangeUser(Row):
    table = "change_users"

    defaults = dict(
        changeid = None,
        uid = None,
    )

    required_columns = ('changeid',)

class Patch(Row):
    table = "patches"

    defaults = dict(
        id = None,
        patchlevel = 0,
        patch_base64 = 'aGVsbG8sIHdvcmxk', # 'hello, world',
        patch_author = None,
        patch_comment = None,
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

class SourceStampSet(Row):
    table = "sourcestampsets"
    defaults = dict(
        id = None,
    )
    id_column = 'id'

class SourceStamp(Row):
    table = "sourcestamps"

    defaults = dict(
        id = None,
        branch = 'master',
        revision = 'abcd',
        patchid = None,
        repository = 'repo',
        codebase = '',
        project = 'proj',
        sourcestampsetid = None,
    )

    id_column = 'id'


class SchedulerChange(Row):
    table = "scheduler_changes"

    defaults = dict(
        objectid = None,
        changeid = None,
        important = 1,
    )

    required_columns = ( 'objectid', 'changeid' )


class Buildset(Row):
    table = "buildsets"

    defaults = dict(
        id = None,
        external_idstring = 'extid',
        reason = 'because',
        sourcestampsetid = None,
        submitted_at = 12345678,
        complete = 0,
        complete_at = None,
        results = -1,
    )

    id_column = 'id'
    required_columns = ( 'sourcestampsetid', )


class BuildsetProperty(Row):
    table = "buildset_properties"

    defaults = dict(
        buildsetid = None,
        property_name = 'prop',
        property_value = '[22, "fakedb"]',
    )

    required_columns = ( 'buildsetid', )


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

class User(Row):
    table = "users"

    defaults = dict(
        uid = None,
        identifier = 'soap',
        bb_username = None,
        bb_password = None,
    )

    id_column = 'uid'

class UserInfo(Row):
    table = "users_info"

    defaults = dict(
        uid = None,
        attr_type = 'git',
        attr_data = 'Tyler Durden <tyler@mayhem.net>',
    )

    required_columns = ( 'uid', )

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

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Change):
                self.changes[row.changeid] = row

            elif isinstance(row, ChangeFile):
                ch = self.changes[row.changeid]
                ch.files.append(row.filename)

            elif isinstance(row, ChangeProperty):
                ch = self.changes[row.changeid]
                n, vs = row.property_name, row.property_value
                v, s = json.loads(vs)
                ch.properties.setProperty(n, v, s)

            elif isinstance(row, ChangeUser):
                ch = self.changes[row.changeid]
                ch.uid = row.uid

    # component methods

    def addChange(self, author=None, files=None, comments=None, is_dir=0,
            revision=None, when_timestamp=None, branch=None,
            category=None, revlink='', properties={}, repository='',
            project='', codebase='', uid=None):
        if self.changes:
            changeid = max(self.changes.iterkeys()) + 1
        else:
            changeid = 500

        self.changes[changeid] = ch = Change(
            changeid=changeid,
            author=author,
            comments=comments,
            is_dir=is_dir,
            revision=revision,
            when_timestamp=datetime2epoch(when_timestamp),
            branch=branch,
            category=category,
            revlink=revlink,
            repository=repository,
            project=project,
            codebase=codebase)
        ch.files = files
        ch.properties = properties

        return defer.succeed(changeid)

    def getLatestChangeid(self):
        if self.changes:
            return defer.succeed(max(self.changes.iterkeys()))
        return defer.succeed(None)

    def getChange(self, changeid):
        try:
            row = self.changes[changeid]
        except KeyError:
            return defer.succeed(None)

        chdict = dict(
                changeid=row.changeid,
                author=row.author,
                files=row.files,
                comments=row.comments,
                is_dir=row.is_dir,
                revision=row.revision,
                when_timestamp=epoch2datetime(row.when_timestamp),
                branch=row.branch,
                category=row.category,
                revlink=row.revlink,
                properties=row.properties,
                repository=row.repository,
                codebase=row.codebase,
                project=row.project)

        return defer.succeed(chdict)

    def getChangeUids(self, changeid):
        try:
            ch_uids = [self.changes[changeid].uid]
        except KeyError:
            ch_uids = []
        return defer.succeed(ch_uids)

    # TODO: getRecentChanges

    # fake methods

    def fakeAddChangeInstance(self, change):
        if not hasattr(change, 'number') or not change.number:
            if self.changes:
                changeid = max(self.changes.iterkeys()) + 1
            else:
                changeid = 500
        else:
            changeid = change.number

        # make a row from the change
        row = dict(
            changeid=changeid,
            author=change.who,
            files=change.files,
            comments=change.comments,
            is_dir=change.isdir,
            revision=change.revision,
            when_timestamp=change.when,
            branch=change.branch,
            category=change.category,
            revlink=change.revlink,
            properties=change.properties,
            repository=change.repository,
            project=change.project)
        self.changes[changeid] = row

class FakeSchedulersComponent(FakeDBComponent):

    def setUp(self):
        self.states = {}
        self.classifications = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, SchedulerChange):
                cls = self.classifications.setdefault(row.objectid, {})
                cls[row.changeid] = row.important

    # component methods

    def classifyChanges(self, objectid, classifications):
        self.classifications.setdefault(objectid, {}).update(classifications)
        return defer.succeed(None)

    def flushChangeClassifications(self, objectid, less_than=None):
        if less_than is not None:
            classifications = self.classifications.setdefault(objectid, {})
            for changeid in classifications.keys():
                if changeid < less_than:
                    del classifications[changeid]
        else:
            self.classifications[objectid] = {}
        return defer.succeed(None)

    def getChangeClassifications(self, objectid, branch=-1):
        classifications = self.classifications.setdefault(objectid, {})
        if branch is not -1:
            # filter out the classifications for the requested branch
            change_branches = dict(
                    (id, c['branch'])
                    for id, c in self.db.changes.changes.iteritems() )
            classifications = dict(
                    (k,v) for (k,v) in classifications.iteritems()
                    if k in change_branches and change_branches[k] == branch )
        return defer.succeed(classifications)

    # fake methods

    def fakeClassifications(self, objectid, classifications):
        """Set the set of classifications for a scheduler"""
        self.classifications[objectid] = classifications

    # assertions

    def assertClassifications(self, objectid, classifications):
        self.t.assertEqual(
                self.classifications.get(objectid, {}),
                classifications)


class FakeSourceStampSetsComponent(FakeDBComponent):
    def setUp(self):
        self.sourcestampsets = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, SourceStampSet):
                self.sourcestampsets[row.id] = dict()

    def addSourceStampSet(self):
        id = len(self.sourcestampsets) + 100
        while id in self.sourcestampsets:
            id += 1
        self.sourcestampsets[id] = dict()
        return defer.succeed(id)

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
                    patch_author=row.patch_author,
                    patch_comment=row.patch_comment,
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

    def addSourceStamp(self, branch, revision, repository, project, sourcestampsetid,
                          codebase = '', patch_body=None, patch_level=0, patch_author=None,
                          patch_comment=None, patch_subdir=None, changeids=[]):
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
                patch_author=patch_author,
                patch_comment=patch_comment
            )
        else:
            patchid = None

        self.sourcestamps[id] = dict(id=id, sourcestampsetid=sourcestampsetid, branch=branch, revision=revision, codebase=codebase,
                patchid=patchid, repository=repository, project=project,
                changeids=changeids)
        return defer.succeed(id)

    def getSourceStamp(self, ssid):
        return defer.succeed(self._getSourceStamp(ssid))

    def _getSourceStamp(self, ssid):
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
                ssdict['patch_author'] = None
                ssdict['patch_comment'] = None
            del ssdict['patchid']
            return ssdict
        else:
            return None

    def getSourceStamps(self, sourcestampsetid):
        sslist = []
        for ssdict in self.sourcestamps.itervalues():
            if ssdict['sourcestampsetid'] == sourcestampsetid:
                ssdictcpy = self._getSourceStamp(ssdict['id'])
                sslist.append(ssdictcpy)
        return defer.succeed(sslist)

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

    def addBuildset(self, sourcestampsetid, reason, properties, builderNames,
                   external_idstring=None, _reactor=reactor):
        bsid = self._newBsid()
        br_rows = []
        for buildername in builderNames:
            br_rows.append(
                    BuildRequest(buildsetid=bsid, buildername=buildername))
        self.db.buildrequests.insertTestData(br_rows)

        # make up a row and keep its dictionary, with the properties tacked on
        bsrow = Buildset(sourcestampsetid=sourcestampsetid, reason=reason, external_idstring=external_idstring)
        self.buildsets[bsid] = bsrow.values.copy()
        self.buildsets[bsid]['properties'] = properties

        return defer.succeed((bsid,
            dict([ (br.buildername, br.id) for br in br_rows ])))

    def completeBuildset(self, bsid, results, complete_at=None,
            _reactor=reactor):
        self.buildsets[bsid]['results'] = results
        self.buildsets[bsid]['complete'] = 1
        self.buildsets[bsid]['complete_at'] = complete_at or _reactor.seconds()
        return defer.succeed(None)

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

    def assertBuildset(self, bsid, expected_buildset, expected_sourcestamps):
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

        dictOfssDict= {}
        for sourcestamp in self.db.sourcestamps.sourcestamps.itervalues():
            if sourcestamp['sourcestampsetid'] == buildset['sourcestampsetid']:
                ssdict = sourcestamp.copy()
                ss_repository = ssdict['codebase']
                dictOfssDict[ss_repository] = ssdict

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
            buildset['brids'] = self.allBuildRequests(bsid)

        for ss in dictOfssDict.itervalues():
            if 'id' in ss:
                del ss['id']
            if not ss['changeids']:
                del ss['changeids']

            # incorporate patch info if we have it
            if 'patchid' in ss and ss['patchid']:
                ss.update(self.db.sourcestamps.patches[ss['patchid']])
            del ss['patchid']

        self.t.assertEqual(
            dict(buildset=buildset, sourcestamps=dictOfssDict),
            dict(buildset=expected_buildset, sourcestamps=expected_sourcestamps))
        return bsid

    def allBuildsetIds(self):
        return self.buildsets.keys()

    def allBuildRequests(self, bsid=None):
        if bsid is not None:
            is_same_bsid = lambda br: br.buildsetid==bsid
        else:
            is_same_bsid = lambda br: True
        return dict([ (br.buildername, br.id)
              for br in self.db.buildrequests.reqs.values()
              if is_same_bsid(br) ])


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
                return defer.succeed(default)
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

    def assertState(self, objectid, missing_keys=[], **kwargs):
        state = self.states[objectid]
        for k in missing_keys:
            self.t.assertFalse(k in state, "%s in %s" % (k, state))
        for k,v in kwargs.iteritems():
            self.t.assertIn(k, state)
            self.t.assertEqual(json.loads(state[k]), v,
                    "state is %r" % (state,))

    def assertStateByClass(self, name, class_name, **kwargs):
        objectid = self.objects[(name, class_name)]
        state = self.states[objectid]
        for k,v in kwargs.iteritems():
            self.t.assertIn(k, state)
            self.t.assertEqual(json.loads(state[k]), v,
                    "state is %r" % (state,))


class FakeBuildRequestsComponent(FakeDBComponent):

    # for use in determining "my" requests
    MASTER_ID = 824

    # override this to set reactor.seconds
    _reactor = reactor

    def setUp(self):
        self.reqs = {}
        self.claims = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, BuildRequest):
                self.reqs[row.id] = row

            if isinstance(row, BuildRequestClaim):
                self.claims[row.brid] = row

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
                claim_row = self.claims.get(br.id)
                if claimed == "mine":
                    if not claim_row or claim_row.objectid != self.MASTER_ID:
                        continue
                elif claimed:
                    if not claim_row:
                        continue
                else:
                    if claim_row:
                        continue
            if bsid is not None:
                if br.buildsetid != bsid:
                    continue
            rv.append(self._brdictFromRow(br))
        return defer.succeed(rv)

    def claimBuildRequests(self, brids, claimed_at=None):
        for brid in brids:
            if brid not in self.reqs or brid in self.claims:
                return defer.fail(
                        failure.Failure(buildrequests.AlreadyClaimedError))

        claimed_at = datetime2epoch(claimed_at)
        if not claimed_at:
            claimed_at = self._reactor.seconds()

        # now that we've thrown any necessary exceptions, get started
        for brid in brids:
            self.claims[brid] = BuildRequestClaim(brid=brid,
                objectid=self.MASTER_ID, claimed_at=claimed_at)
        return defer.succeed(None)

    def reclaimBuildRequests(self, brids):
        for brid in brids:
            if brid not in self.claims:
                print "trying to reclaim brid %d, but it's not claimed" % brid
                return defer.fail(
                        failure.Failure(buildrequests.AlreadyClaimedError))
        # now that we've thrown any necessary exceptions, get started
        for brid in brids:
            self.claims[brid] = BuildRequestClaim(brid=brid,
                objectid=self.MASTER_ID, claimed_at=self._reactor.seconds())
        return defer.succeed(None)

    # Code copied from buildrequests.BuildRequestConnectorComponent
    def _brdictFromRow(self, row):
        claimed = mine = False
        claimed_at = None
        claim_row = self.claims.get(row.id, None)
        if claim_row:
            claimed = True
            claimed_at = claim_row.claimed_at
            mine = claim_row.objectid == self.MASTER_ID

        submitted_at = epoch2datetime(row.submitted_at)
        complete_at = epoch2datetime(row.complete_at)

        return dict(brid=row.id, buildsetid=row.buildsetid,
                buildername=row.buildername, priority=row.priority,
                claimed=claimed, claimed_at=claimed_at, mine=mine,
                complete=bool(row.complete), results=row.results,
                submitted_at=submitted_at, complete_at=complete_at)

    # fake methods

    def fakeClaimBuildRequest(self, brid, claimed_at=None, objectid=None):
        if objectid is None:
            objectid = self.MASTER_ID
        self.claims[brid] = BuildRequestClaim(brid=brid,
            objectid=objectid, claimed_at=self._reactor.seconds())

    def fakeUnclaimBuildRequest(self, brid):
        del self.claims[brid]

    # assertions

    def assertMyClaims(self, claimed_brids):
        self.t.assertEqual(
                [ id for (id, brc) in self.claims.iteritems()
                  if brc.objectid == self.MASTER_ID ],
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

        return defer.succeed(dict(
            bid=row.id,
            brid=row.brid,
            number=row.number,
            start_time=epoch2datetime(row.start_time),
            finish_time=epoch2datetime(row.finish_time)))
    
    def getBuildsForRequest(self, brid):
        ret = []
 
        for (id, row) in self.builds.items():
            if row.brid == brid:
                ret.append(dict(bid = row.id,
                                brid=row.brid,
                                number=row.number,
                                start_time=epoch2datetime(row.start_time),
                                finish_time=epoch2datetime(row.finish_time)))
               
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

class FakeUsersComponent(FakeDBComponent):

    def setUp(self):
        self.users = {}
        self.users_info = {}
        self.id_num = 0

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, User):
                self.users[row.uid] = dict(identifier=row.identifier,
                                           bb_username=row.bb_username,
                                           bb_password=row.bb_password)

            if isinstance(row, UserInfo):
                assert row.uid in self.users
                if row.uid not in self.users_info:
                    self.users_info[row.uid] = [dict(attr_type=row.attr_type,
                                                     attr_data=row.attr_data)]
                else:
                    self.users_info[row.uid].append(
                                                dict(attr_type=row.attr_type,
                                                     attr_data=row.attr_data))

    def _user2dict(self, uid):
        usdict = None
        if uid in self.users:
            usdict = self.users[uid]
            if uid in self.users_info:
                infos = self.users_info[uid]
                for attr in infos:
                    usdict[attr['attr_type']] = attr['attr_data']
            usdict['uid'] = uid
        return usdict

    def nextId(self):
        self.id_num += 1
        return self.id_num

    # component methods

    def findUserByAttr(self, identifier, attr_type, attr_data):
        for uid in self.users_info:
            attrs = self.users_info[uid]
            for attr in attrs:
                if (attr_type == attr['attr_type'] and
                    attr_data == attr['attr_data']):
                    return defer.succeed(uid)

        uid = self.nextId()
        self.db.insertTestData([User(uid=uid, identifier=identifier)])
        self.db.insertTestData([UserInfo(uid=uid,
                                         attr_type=attr_type,
                                         attr_data=attr_data)])
        return defer.succeed(uid)

    def getUser(self, uid):
        usdict = None
        if uid in self.users:
            usdict = self._user2dict(uid)
        return defer.succeed(usdict)

    def getUserByUsername(self, username):
        usdict = None
        for uid in self.users:
            user = self.users[uid]
            if user['bb_username'] == username:
                usdict = self._user2dict(uid)
        return defer.succeed(usdict)

    def updateUser(self, uid=None, identifier=None, bb_username=None,
                   bb_password=None, attr_type=None, attr_data=None):
        assert uid is not None

        if identifier is not None:
            self.users[uid]['identifier'] = identifier

        if bb_username is not None:
            assert bb_password is not None
            try:
                user = self.users[uid]
                user['bb_username'] = bb_username
                user['bb_password'] = bb_password
            except KeyError:
                pass

        if attr_type is not None:
            assert attr_data is not None
            try:
                infos = self.users_info[uid]
                for attr in infos:
                    if attr_type == attr['attr_type']:
                        attr['attr_data'] = attr_data
                        break
                else:
                    infos.append(dict(attr_type=attr_type,
                                      attr_data=attr_data))
            except KeyError:
                pass

        return defer.succeed(None)

    def removeUser(self, uid):
        if uid in self.users:
            self.users.pop(uid)
            self.users_info.pop(uid)
        return defer.succeed(None)

    def identifierToUid(self, identifier):
        for uid in self.users:
            if identifier == self.users[uid]['identifier']:
                return defer.succeed(uid)
        return defer.succeed(None)

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
        self.sourcestampsets = comp = FakeSourceStampSetsComponent(self,testcase)
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
        self.users = comp = FakeUsersComponent(self, testcase)
        self._components.append(comp)

    def setup(self):
        self.is_setup = True
        return defer.succeed(None)

    def insertTestData(self, rows):
        """Insert a list of Row instances into the database; this method can be
        called synchronously or asynchronously (it completes immediately) """
        for comp in self._components:
            comp.insertTestData(rows)
        return defer.succeed(None)
