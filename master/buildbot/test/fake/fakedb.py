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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems
from future.utils import itervalues
from future.utils import text_type

import base64
import copy
import hashlib
import json

from twisted.internet import defer
from twisted.internet import reactor

from buildbot.data import resultspec
from buildbot.db import buildrequests
from buildbot.db import changesources
from buildbot.db import schedulers
from buildbot.test.util import validation
from buildbot.util import bytes2NativeString
from buildbot.util import datetime2epoch
from buildbot.util import service
from buildbot.util import unicode2bytes

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

    @cvar hashedColumns: a tuple of hash column and source columns designating
    a hash to work around MySQL's inability to do indexing.

    @ivar values: the values to be inserted into this row
    """

    id_column = ()
    required_columns = ()
    lists = ()
    dicts = ()
    hashedColumns = []
    foreignKeys = []
    # Columns that content is represented as sa.Binary-like type in DB model.
    # They value is bytestring (in contrast to text-like columns, which are
    # unicode).
    binary_columns = ()

    _next_id = None

    def __init__(self, **kwargs):
        self.values = self.defaults.copy()
        self.values.update(kwargs)
        if self.id_column:
            if self.values[self.id_column] is None:
                self.values[self.id_column] = self.nextId()
        for col in self.required_columns:
            assert col in kwargs, "%s not specified: %s" % (col, kwargs)
        for col in self.lists:
            setattr(self, col, [])
        for col in self.dicts:
            setattr(self, col, {})
        for col in kwargs:
            assert col in self.defaults, "%s is not a valid column" % col
        # cast to unicode
        for k, v in iteritems(self.values):
            if isinstance(v, str):
                self.values[k] = text_type(v)
        # Binary columns stores either (compressed) binary data or encoded
        # with utf-8 unicode string. We assume that Row constructor receives
        # only unicode strings and encode them to utf-8 here.
        # At this moment there is only one such column: logchunks.contents,
        # which stores either utf-8 encoded string, or gzip-compressed
        # utf-8 encoded string.
        for col in self.binary_columns:
            self.values[col] = unicode2bytes(self.values[col])
        # calculate any necessary hashes
        for hash_col, src_cols in self.hashedColumns:
            self.values[hash_col] = self.hashColumns(
                *(self.values[c] for c in src_cols))

        # make the values appear as attributes
        self.__dict__.update(self.values)

    def __eq__(self, other):
        if self.__class__ != other.__class__:
            return False
        return self.values == other.values

    def __ne__(self, other):
        if self.__class__ != other.__class__:
            return True
        return self.values != other.values

    def __lt__(self, other):
        if self.__class__ != other.__class__:
            raise TypeError("Cannot compare {} and {}".format(
                self.__class__, other.__class__))
        return self.values < other.values

    def __le__(self, other):
        if self.__class__ != other.__class__:
            raise TypeError("Cannot compare {} and {}".format(
                self.__class__, other.__class__))
        return self.values <= other.values

    def __gt__(self, other):
        if self.__class__ != other.__class__:
            raise TypeError("Cannot compare {} and {}".format(
                self.__class__, other.__class__))
        return self.values > other.values

    def __ge__(self, other):
        if self.__class__ != other.__class__:
            raise TypeError("Cannot compare {} and {}".format(
                self.__class__, other.__class__))
        return self.values >= other.values

    def __repr__(self):
        return '%s(**%r)' % (self.__class__.__name__, self.values)

    def nextId(self):
        id = Row._next_id if Row._next_id is not None else 1
        Row._next_id = id + 1
        return id

    def hashColumns(self, *args):
        # copied from master/buildbot/db/base.py
        def encode(x):
            if x is None:
                return b'\xf5'
            elif isinstance(x, text_type):
                return x.encode('utf-8')
            return str(x).encode('utf-8')

        return hashlib.sha1(b'\0'.join(map(encode, args))).hexdigest()

    @defer.inlineCallbacks
    def checkForeignKeys(self, db, t):
        accessors = dict(
            buildsetid=db.buildsets.getBuildset,
            workerid=db.workers.getWorker,
            builderid=db.builders.getBuilder,
            buildid=db.builds.getBuild,
            changesourceid=db.changesources.getChangeSource,
            changeid=db.changes.getChange,
            buildrequestid=db.buildrequests.getBuildRequest,
            sourcestampid=db.sourcestamps.getSourceStamp,
            schedulerid=db.schedulers.getScheduler,
            brid=db.buildrequests.getBuildRequest,
            masterid=db.masters.getMaster)
        for foreign_key in self.foreignKeys:
            if foreign_key in accessors:
                key = getattr(self, foreign_key)
                if key is not None:
                    val = yield accessors[foreign_key](key)
                    t.assertTrue(val is not None,
                                 "foreign key %s:%r does not exit" % (foreign_key, key))
            else:
                raise ValueError(
                    "warning, unsupported foreign key", foreign_key, self.table)


class BuildRequest(Row):
    table = "buildrequests"

    defaults = dict(
        id=None,
        buildsetid=None,
        builderid=None,
        buildername=None,
        priority=0,
        complete=0,
        results=-1,
        submitted_at=12345678,
        complete_at=None,
        waited_for=0,
    )
    foreignKeys = ('buildsetid',)

    id_column = 'id'
    required_columns = ('buildsetid',)


class BuildRequestClaim(Row):
    table = "buildrequest_claims"

    defaults = dict(
        brid=None,
        masterid=None,
        claimed_at=None
    )
    foreignKeys = ('brid', 'masterid')

    required_columns = ('brid', 'masterid', 'claimed_at')


class ChangeSource(Row):
    table = "changesources"

    defaults = dict(
        id=None,
        name='csname',
        name_hash=None,
    )

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]


class ChangeSourceMaster(Row):
    table = "changesource_masters"

    defaults = dict(
        changesourceid=None,
        masterid=None,
    )

    foreignKeys = ('changesourceid', 'masterid')
    required_columns = ('changesourceid', 'masterid')


class Change(Row):
    table = "changes"

    defaults = dict(
        changeid=None,
        author=u'frank',
        comments=u'test change',
        branch=u'master',
        revision=u'abcd',
        revlink=u'http://vc/abcd',
        when_timestamp=1200000,
        category=u'cat',
        repository=u'repo',
        codebase=u'',
        project=u'proj',
        sourcestampid=92,
        parent_changeids=None,
    )

    lists = ('files', 'uids')
    dicts = ('properties',)
    id_column = 'changeid'


class ChangeFile(Row):
    table = "change_files"

    defaults = dict(
        changeid=None,
        filename=None,
    )

    foreignKeys = ('changeid',)
    required_columns = ('changeid',)


class ChangeProperty(Row):
    table = "change_properties"

    defaults = dict(
        changeid=None,
        property_name=None,
        property_value=None,
    )

    foreignKeys = ('changeid',)
    required_columns = ('changeid',)


class ChangeUser(Row):
    table = "change_users"

    defaults = dict(
        changeid=None,
        uid=None,
    )

    foreignKeys = ('changeid',)
    required_columns = ('changeid',)


class Patch(Row):
    table = "patches"

    defaults = dict(
        id=None,
        patchlevel=0,
        patch_base64='aGVsbG8sIHdvcmxk',  # 'hello, world',
        patch_author=None,
        patch_comment=None,
        subdir=None,
    )

    id_column = 'id'


class SourceStamp(Row):
    table = "sourcestamps"

    defaults = dict(
        id=None,
        branch='master',
        revision='abcd',
        patchid=None,
        repository='repo',
        codebase='',
        project='proj',
        created_at=89834834,
        ss_hash=None,
    )

    id_column = 'id'
    hashedColumns = [('ss_hash', ('branch', 'revision', 'repository',
                                  'project', 'codebase', 'patchid',))]


class Scheduler(Row):
    table = "schedulers"

    defaults = dict(
        id=None,
        name='schname',
        name_hash=None,
        enabled=1,
    )

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]


class SchedulerMaster(Row):
    table = "scheduler_masters"

    defaults = dict(
        schedulerid=None,
        masterid=None,
    )

    foreignKeys = ('schedulerid', 'masterid')
    required_columns = ('schedulerid', 'masterid')


class SchedulerChange(Row):
    table = "scheduler_changes"

    defaults = dict(
        schedulerid=None,
        changeid=None,
        important=1,
    )

    foreignKeys = ('schedulerid', 'changeid')
    required_columns = ('schedulerid', 'changeid')


class Buildset(Row):
    table = "buildsets"

    defaults = dict(
        id=None,
        external_idstring='extid',
        reason='because',
        submitted_at=12345678,
        complete=0,
        complete_at=None,
        results=-1,
        parent_buildid=None,
        parent_relationship=None,
    )

    id_column = 'id'


class BuildsetProperty(Row):
    table = "buildset_properties"

    defaults = dict(
        buildsetid=None,
        property_name='prop',
        property_value='[22, "fakedb"]',
    )

    foreignKeys = ('buildsetid',)
    required_columns = ('buildsetid', )


class Worker(Row):
    table = "workers"

    defaults = dict(
        id=None,
        name='some:worker',
        info={"a": "b"},
    )

    id_column = 'id'
    required_columns = ('name', )


class BuildsetSourceStamp(Row):
    table = "buildset_sourcestamps"

    defaults = dict(
        id=None,
        buildsetid=None,
        sourcestampid=None,
    )

    foreignKeys = ('buildsetid', 'sourcestampid')
    required_columns = ('buildsetid', 'sourcestampid', )
    id_column = 'id'


class Object(Row):
    table = "objects"

    defaults = dict(
        id=None,
        name='nam',
        class_name='cls',
    )

    id_column = 'id'


class ObjectState(Row):
    table = "object_state"

    defaults = dict(
        objectid=None,
        name='nam',
        value_json='{}',
    )

    required_columns = ('objectid', )


class User(Row):
    table = "users"

    defaults = dict(
        uid=None,
        identifier='soap',
        bb_username=None,
        bb_password=None,
    )

    id_column = 'uid'


class UserInfo(Row):
    table = "users_info"

    defaults = dict(
        uid=None,
        attr_type='git',
        attr_data='Tyler Durden <tyler@mayhem.net>',
    )

    foreignKeys = ('uid',)
    required_columns = ('uid', )


class Build(Row):
    table = "builds"

    defaults = dict(
        id=None,
        number=29,
        buildrequestid=None,
        builderid=None,
        workerid=-1,
        masterid=None,
        started_at=1304262222,
        complete_at=None,
        state_string=u"test",
        results=None)

    id_column = 'id'
    foreignKeys = ('buildrequestid', 'masterid', 'workerid', 'builderid')
    required_columns = ('buildrequestid', 'masterid', 'workerid')


class BuildProperty(Row):
    table = "build_properties"
    defaults = dict(
        buildid=None,
        name='prop',
        value=42,
        source='fakedb'
    )

    foreignKeys = ('buildid',)
    required_columns = ('buildid',)


class Step(Row):
    table = "steps"

    defaults = dict(
        id=None,
        number=29,
        name='step29',
        buildid=None,
        started_at=1304262222,
        complete_at=None,
        state_string='',
        results=None,
        urls_json='[]',
        hidden=0)

    id_column = 'id'
    foreignKeys = ('buildid',)
    required_columns = ('buildid', )


class Log(Row):
    table = "logs"

    defaults = dict(
        id=None,
        name='log29',
        slug='log29',
        stepid=None,
        complete=0,
        num_lines=0,
        type='s')

    id_column = 'id'
    required_columns = ('stepid', )


class LogChunk(Row):
    table = "logchunks"

    defaults = dict(
        logid=None,
        first_line=0,
        last_line=0,
        content=u'',
        compressed=0)

    required_columns = ('logid', )
    # 'content' column is sa.LargeBinary, it's bytestring.
    binary_columns = ('content',)


class Master(Row):
    table = "masters"

    defaults = dict(
        id=None,
        name='some:master',
        name_hash=None,
        active=1,
        last_active=9998999,
    )

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]


class Builder(Row):
    table = "builders"

    defaults = dict(
        id=None,
        name='some:builder',
        name_hash=None,
        description=None,
    )

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]


class BuilderMaster(Row):
    table = "builder_masters"

    defaults = dict(
        id=None,
        builderid=None,
        masterid=None
    )

    id_column = 'id'
    required_columns = ('builderid', 'masterid')


class Tag(Row):
    table = "tags"

    defaults = dict(
        id=None,
        name='some:tag',
        name_hash=None,
    )

    id_column = 'id'
    hashedColumns = [('name_hash', ('name',))]


class BuildersTags(Row):
    table = "builders_tags"

    defaults = dict(
        id=None,
        builderid=None,
        tagid=None,
    )

    foreignKeys = ('builderid', 'tagid')
    required_columns = ('builderid', 'tagid', )
    id_column = 'id'


class ConnectedWorker(Row):
    table = "connected_workers"

    defaults = dict(
        id=None,
        masterid=None,
        workerid=None,
    )

    id_column = 'id'
    required_columns = ('masterid', 'workerid')


class ConfiguredWorker(Row):
    table = "configured_workers"

    defaults = dict(
        id=None,
        buildermasterid=None,
        workerid=None,
    )

    id_column = 'id'
    required_columns = ('buildermasterid', 'workerid')

# Fake DB Components


class FakeDBComponent(object):
    data2db = {}

    def __init__(self, db, testcase):
        self.db = db
        self.t = testcase
        self.setUp()

    def mapFilter(self, f, fieldMapping):
        field = fieldMapping[f.field].split(".")[-1]
        return resultspec.Filter(field, f.op, f.values)

    def mapOrder(self, o, fieldMapping):
        if o.startswith('-'):
            reverse, o = o[0], o[1:]
        else:
            reverse = ""
        o = fieldMapping[o].split(".")[-1]
        return reverse + o

    def applyResultSpec(self, data, rs):
        def applicable(field):
            if field.startswith('-'):
                field = field[1:]
            return field in rs.fieldMapping
        filters = [self.mapFilter(f, rs.fieldMapping)
                   for f in rs.filters if applicable(f.field)]
        order = []
        offset = limit = None
        if rs.order:
            order = [self.mapOrder(o, rs.fieldMapping)
                     for o in rs.order if applicable(o)]
        if len(filters) == len(rs.filters) and rs.order is not None and len(order) == len(rs.order):
            offset, limit = rs.offset, rs.limit
        rs = resultspec.ResultSpec(
            filters=filters, order=order, limit=limit, offset=offset)
        return rs.apply(data)


class FakeChangeSourcesComponent(FakeDBComponent):

    def setUp(self):
        self.changesources = {}
        self.changesource_masters = {}
        self.states = {}

    def insertTestData(self, rows):
        pass
        for row in rows:
            if isinstance(row, ChangeSource):
                self.changesources[row.id] = row.name
            if isinstance(row, ChangeSourceMaster):
                self.changesource_masters[row.changesourceid] = row.masterid

    # component methods

    def findChangeSourceId(self, name):
        for cs_id, cs_name in iteritems(self.changesources):
            if cs_name == name:
                return defer.succeed(cs_id)
        new_id = (max(self.changesources) + 1) if self.changesources else 1
        self.changesources[new_id] = name
        return defer.succeed(new_id)

    def getChangeSource(self, changesourceid):
        if changesourceid in self.changesources:
            rv = dict(
                id=changesourceid,
                name=self.changesources[changesourceid],
                masterid=None)
            # only set masterid if the relevant changesource master exists and
            # is active
            rv['masterid'] = self.changesource_masters.get(changesourceid)
            return defer.succeed(rv)
        return None

    def getChangeSources(self, active=None, masterid=None):
        d = defer.DeferredList([
            self.getChangeSource(id) for id in self.changesources
        ])

        @d.addCallback
        def filter(results):
            # filter off the DeferredList results (we know it's good)
            results = [r[1] for r in results]
            # filter for masterid
            if masterid is not None:
                results = [r for r in results
                           if r['masterid'] == masterid]
            # filter for active or inactive if necessary
            if active:
                results = [r for r in results
                           if r['masterid'] is not None]
            elif active is not None:
                results = [r for r in results
                           if r['masterid'] is None]
            return results
        return d

    def setChangeSourceMaster(self, changesourceid, masterid):
        current_masterid = self.changesource_masters.get(changesourceid)
        if current_masterid and masterid is not None and current_masterid != masterid:
            return defer.fail(changesources.ChangeSourceAlreadyClaimedError())
        self.changesource_masters[changesourceid] = masterid
        return defer.succeed(None)

    # fake methods

    def fakeChangeSource(self, name, changesourceid):
        self.changesources[changesourceid] = name

    def fakeChangeSourceMaster(self, changesourceid, masterid):
        if masterid is not None:
            self.changesource_masters[changesourceid] = masterid
        else:
            del self.changesource_masters[changesourceid]

    # assertions

    def assertChangeSourceMaster(self, changesourceid, masterid):
        self.t.assertEqual(self.changesource_masters.get(changesourceid),
                           masterid)


class FakeChangesComponent(FakeDBComponent):

    def setUp(self):
        self.changes = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Change):
                # copy this since we'll be modifying it (e.g., adding files)
                ch = self.changes[row.changeid] = copy.deepcopy(row.values)
                ch['files'] = []
                ch['properties'] = {}
                ch['uids'] = []

            elif isinstance(row, ChangeFile):
                ch = self.changes[row.changeid]
                ch['files'].append(row.filename)

            elif isinstance(row, ChangeProperty):
                ch = self.changes[row.changeid]
                n, vs = row.property_name, row.property_value
                v, s = json.loads(vs)
                ch['properties'][n] = (v, s)

            elif isinstance(row, ChangeUser):
                ch = self.changes[row.changeid]
                ch['uids'].append(row.uid)

    # component methods

    @defer.inlineCallbacks
    def addChange(self, author=None, files=None, comments=None, is_dir=None,
                  revision=None, when_timestamp=None, branch=None,
                  category=None, revlink='', properties=None, repository='',
                  codebase='', project='', uid=None, _reactor=reactor):
        if properties is None:
            properties = {}

        if self.changes:
            changeid = max(list(self.changes)) + 1
        else:
            changeid = 500

        ssid = yield self.db.sourcestamps.findSourceStampId(
            revision=revision, branch=branch, repository=repository,
            codebase=codebase, project=project, _reactor=_reactor)

        parent_changeids = yield self.getParentChangeIds(branch, repository, project, codebase)

        self.changes[changeid] = ch = dict(
            changeid=changeid,
            parent_changeids=parent_changeids,
            author=author,
            comments=comments,
            revision=revision,
            when_timestamp=datetime2epoch(when_timestamp),
            branch=branch,
            category=category,
            revlink=revlink,
            repository=repository,
            project=project,
            codebase=codebase,
            uids=[],
            files=files,
            properties=properties,
            sourcestampid=ssid)

        if uid:
            ch['uids'].append(uid)

        defer.returnValue(changeid)

    def getLatestChangeid(self):
        if self.changes:
            return defer.succeed(max(list(self.changes)))
        return defer.succeed(None)

    def getParentChangeIds(self, branch, repository, project, codebase):
        if self.changes:
            for changeid, change in iteritems(self.changes):
                if (change['branch'] == branch and
                        change['repository'] == repository and
                        change['project'] == project and
                        change['codebase'] == codebase):
                    return defer.succeed([change['changeid']])
        return defer.succeed([])

    def getChange(self, key, no_cache=False):
        try:
            row = self.changes[key]
        except KeyError:
            return defer.succeed(None)

        return defer.succeed(self._chdict(row))

    def getChangeUids(self, changeid):
        try:
            ch_uids = self.changes[changeid]['uids']
        except KeyError:
            ch_uids = []
        return defer.succeed(ch_uids)

    def getRecentChanges(self, count):
        ids = sorted(self.changes.keys())
        chdicts = [self._chdict(self.changes[id]) for id in ids[-count:]]
        return defer.succeed(chdicts)

    def getChanges(self):
        chdicts = [self._chdict(v) for v in itervalues(self.changes)]
        return defer.succeed(chdicts)

    def getChangesCount(self):
        return defer.succeed(len(self.changes))

    def getChangesForBuild(self, buildid):
        # the algorithm is too complicated to be worth faked, better patch it
        # ad-hoc
        raise NotImplementedError(
            "Please patch in tests to return appropriate results")

    def getChangeFromSSid(self, ssid):
        chdicts = [self._chdict(v) for v in itervalues(
            self.changes) if v['sourcestampid'] == ssid]
        if chdicts:
            return defer.succeed(chdicts[0])
        return defer.succeed(None)

    def _chdict(self, row):
        chdict = row.copy()
        del chdict['uids']
        if chdict['parent_changeids'] is None:
            chdict['parent_changeids'] = []

        chdict['when_timestamp'] = _mkdt(chdict['when_timestamp'])
        return chdict

    # assertions

    def assertChange(self, changeid, row):
        row_only = self.changes[changeid].copy()
        del row_only['files']
        del row_only['properties']
        del row_only['uids']
        if not row_only['parent_changeids']:
            # Convert [] to None
            # None is the value stored in the DB.
            # We need this kind of conversion, because for the moment we only support
            # 1 parent for a change.
            # When we will support multiple parent for change, then we will have a
            # table parent_changes with at least 2 col: "changeid", "parent_changeid"
            # And the col 'parent_changeids' of the table changes will be
            # dropped
            row_only['parent_changeids'] = None
        self.t.assertEqual(row_only, row.values)

    def assertChangeUsers(self, changeid, expectedUids):
        self.t.assertEqual(self.changes[changeid]['uids'], expectedUids)

    # fake methods

    def fakeAddChangeInstance(self, change):
        if not hasattr(change, 'number') or not change.number:
            if self.changes:
                changeid = max(list(self.changes)) + 1
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
            revision=change.revision,
            when_timestamp=change.when,
            branch=change.branch,
            category=change.category,
            revlink=change.revlink,
            properties=change.properties,
            repository=change.repository,
            codebase=change.codebase,
            project=change.project,
            uids=[])
        self.changes[changeid] = row


class FakeSchedulersComponent(FakeDBComponent):

    def setUp(self):
        self.schedulers = {}
        self.scheduler_masters = {}
        self.states = {}
        self.classifications = {}
        self.enabled = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, SchedulerChange):
                cls = self.classifications.setdefault(row.schedulerid, {})
                cls[row.changeid] = row.important
            if isinstance(row, Scheduler):
                self.schedulers[row.id] = row.name
                self.enabled[row.id] = True
            if isinstance(row, SchedulerMaster):
                self.scheduler_masters[row.schedulerid] = row.masterid

    # component methods

    def classifyChanges(self, schedulerid, classifications):
        self.classifications.setdefault(
            schedulerid, {}).update(classifications)
        return defer.succeed(None)

    def flushChangeClassifications(self, schedulerid, less_than=None):
        if less_than is not None:
            classifications = self.classifications.setdefault(schedulerid, {})
            for changeid in list(classifications):
                if changeid < less_than:
                    del classifications[changeid]
        else:
            self.classifications[schedulerid] = {}
        return defer.succeed(None)

    def getChangeClassifications(self, schedulerid, branch=-1, repository=-1,
                                 project=-1, codebase=-1):
        classifications = self.classifications.setdefault(schedulerid, {})

        sentinel = dict(branch=object(), repository=object(),
                        project=object(), codebase=object())

        if branch != -1:
            # filter out the classifications for the requested branch
            classifications = dict(
                (k, v) for (k, v) in iteritems(classifications)
                if self.db.changes.changes.get(k, sentinel)['branch'] == branch)

        if repository != -1:
            # filter out the classifications for the requested branch
            classifications = dict(
                (k, v) for (k, v) in iteritems(classifications)
                if self.db.changes.changes.get(k, sentinel)['repository'] == repository)

        if project != -1:
            # filter out the classifications for the requested branch
            classifications = dict(
                (k, v) for (k, v) in iteritems(classifications)
                if self.db.changes.changes.get(k, sentinel)['project'] == project)

        if codebase != -1:
            # filter out the classifications for the requested branch
            classifications = dict(
                (k, v) for (k, v) in iteritems(classifications)
                if self.db.changes.changes.get(k, sentinel)['codebase'] == codebase)

        return defer.succeed(classifications)

    def findSchedulerId(self, name):
        for sch_id, sch_name in iteritems(self.schedulers):
            if sch_name == name:
                return defer.succeed(sch_id)
        new_id = (max(self.schedulers) + 1) if self.schedulers else 1
        self.schedulers[new_id] = name
        return defer.succeed(new_id)

    def getScheduler(self, schedulerid):
        if schedulerid in self.schedulers:
            rv = dict(
                id=schedulerid,
                name=self.schedulers[schedulerid],
                enabled=self.enabled.get(schedulerid, True),
                masterid=None)
            # only set masterid if the relevant scheduler master exists and
            # is active
            rv['masterid'] = self.scheduler_masters.get(schedulerid)
            return defer.succeed(rv)
        return None

    def getSchedulers(self, active=None, masterid=None):
        d = defer.DeferredList([
            self.getScheduler(id) for id in self.schedulers
        ])

        @d.addCallback
        def filter(results):
            # filter off the DeferredList results (we know it's good)
            results = [r[1] for r in results]
            # filter for masterid
            if masterid is not None:
                results = [r for r in results
                           if r['masterid'] == masterid]
            # filter for active or inactive if necessary
            if active:
                results = [r for r in results
                           if r['masterid'] is not None]
            elif active is not None:
                results = [r for r in results
                           if r['masterid'] is None]
            return results
        return d

    def setSchedulerMaster(self, schedulerid, masterid):
        current_masterid = self.scheduler_masters.get(schedulerid)
        if current_masterid and masterid is not None and current_masterid != masterid:
            return defer.fail(schedulers.SchedulerAlreadyClaimedError())
        self.scheduler_masters[schedulerid] = masterid
        return defer.succeed(None)

    # fake methods

    def fakeClassifications(self, schedulerid, classifications):
        """Set the set of classifications for a scheduler"""
        self.classifications[schedulerid] = classifications

    def fakeScheduler(self, name, schedulerid):
        self.schedulers[schedulerid] = name

    def fakeSchedulerMaster(self, schedulerid, masterid):
        if masterid is not None:
            self.scheduler_masters[schedulerid] = masterid
        else:
            del self.scheduler_masters[schedulerid]

    # assertions

    def assertClassifications(self, schedulerid, classifications):
        self.t.assertEqual(
            self.classifications.get(schedulerid, {}),
            classifications)

    def assertSchedulerMaster(self, schedulerid, masterid):
        self.t.assertEqual(self.scheduler_masters.get(schedulerid),
                           masterid)

    def enable(self, schedulerid, v):
        assert schedulerid in self.schedulers
        self.enabled[schedulerid] = v
        return defer.succeed((('control', 'schedulers', schedulerid, 'enable'), {'enabled': v}))


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
                ss['created_at'] = _mkdt(ss['created_at'])
                del ss['ss_hash']
                del ss['id']

    # component methods

    def findSourceStampId(self, branch=None, revision=None, repository=None,
                          project=None, codebase=None,
                          patch_body=None, patch_level=None,
                          patch_author=None, patch_comment=None, patch_subdir=None,
                          _reactor=reactor):
        if patch_body:
            patchid = len(self.patches) + 1
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

        new_ssdict = dict(branch=branch, revision=revision, codebase=codebase,
                          patchid=patchid, repository=repository, project=project,
                          created_at=_mkdt(_reactor.seconds()))
        for id, ssdict in iteritems(self.sourcestamps):
            keys = ['branch', 'revision', 'repository',
                    'codebase', 'project', 'patchid']
            if [ssdict[k] for k in keys] == [new_ssdict[k] for k in keys]:
                return defer.succeed(id)

        id = len(self.sourcestamps) + 100
        while id in self.sourcestamps:
            id += 1
        self.sourcestamps[id] = new_ssdict
        return defer.succeed(id)

    def getSourceStamp(self, key, no_cache=False):
        return defer.succeed(self._getSourceStamp_sync(key))

    def getSourceStamps(self):
        return defer.succeed([
            self._getSourceStamp_sync(ssid)
            for ssid in self.sourcestamps
        ])

    def _getSourceStamp_sync(self, ssid):
        if ssid in self.sourcestamps:
            ssdict = self.sourcestamps[ssid].copy()
            ssdict['ssid'] = ssid
            patchid = ssdict['patchid']
            if patchid:
                ssdict.update(self.patches[patchid])
                ssdict['patchid'] = patchid
            else:
                ssdict['patch_body'] = None
                ssdict['patch_level'] = None
                ssdict['patch_subdir'] = None
                ssdict['patch_author'] = None
                ssdict['patch_comment'] = None
            return ssdict
        else:
            return None

    @defer.inlineCallbacks
    def getSourceStampsForBuild(self, buildid):
        build = yield self.db.builds.getBuild(buildid)
        breq = yield self.db.buildrequests.getBuildRequest(build['buildrequestid'])
        bset = yield self.db.buildsets.getBuildset(breq['buildsetid'])

        results = []
        for ssid in bset['sourcestamps']:
            results.append((yield self.getSourceStamp(ssid)))
        defer.returnValue(results)


class FakeBuildsetsComponent(FakeDBComponent):

    def setUp(self):
        self.buildsets = {}
        self.completed_bsids = set()
        self.buildset_sourcestamps = {}

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

        for row in rows:
            if isinstance(row, BuildsetSourceStamp):
                assert row.buildsetid in self.buildsets
                self.buildset_sourcestamps.setdefault(row.buildsetid,
                                                      []).append(row.sourcestampid)

    # component methods

    def _newBsid(self):
        bsid = 200
        while bsid in self.buildsets:
            bsid += 1
        return bsid

    @defer.inlineCallbacks
    def addBuildset(self, sourcestamps, reason, properties, builderids, waited_for,
                    external_idstring=None, submitted_at=None,
                    parent_buildid=None, parent_relationship=None,
                    _reactor=reactor):
        # We've gotten this wrong a couple times.
        assert isinstance(
            waited_for, bool), 'waited_for should be boolean: %r' % waited_for

        # calculate submitted at
        if submitted_at:
            submitted_at = datetime2epoch(submitted_at)
        else:
            submitted_at = _reactor.seconds()

        bsid = self._newBsid()
        br_rows = []
        for builderid in builderids:
            br_rows.append(
                BuildRequest(buildsetid=bsid, builderid=builderid, waited_for=waited_for,
                             submitted_at=submitted_at))
        self.db.buildrequests.insertTestData(br_rows)

        # make up a row and keep its dictionary, with the properties tacked on
        bsrow = Buildset(id=bsid, reason=reason,
                         external_idstring=external_idstring,
                         submitted_at=submitted_at,
                         parent_buildid=parent_buildid, parent_relationship=parent_relationship)
        self.buildsets[bsid] = bsrow.values.copy()
        self.buildsets[bsid]['properties'] = properties

        # add sourcestamps
        ssids = []
        for ss in sourcestamps:
            if not isinstance(ss, type(1)):
                ss = yield self.db.sourcestamps.findSourceStampId(**ss)
            ssids.append(ss)
        self.buildset_sourcestamps[bsid] = ssids

        defer.returnValue((bsid,
                           dict([(br.builderid, br.id) for br in br_rows])))

    def completeBuildset(self, bsid, results, complete_at=None,
                         _reactor=reactor):
        if bsid not in self.buildsets or self.buildsets[bsid]['complete']:
            raise KeyError
        self.buildsets[bsid]['results'] = results
        self.buildsets[bsid]['complete'] = 1
        self.buildsets[bsid]['complete_at'] = \
            datetime2epoch(complete_at) if complete_at else _reactor.seconds()
        return defer.succeed(None)

    def getBuildset(self, bsid):
        if bsid not in self.buildsets:
            return defer.succeed(None)
        row = self.buildsets[bsid]
        return defer.succeed(self._row2dict(row))

    def getBuildsets(self, complete=None, resultSpec=None):
        rv = []
        for bs in itervalues(self.buildsets):
            if complete is not None:
                if complete and bs['complete']:
                    rv.append(self._row2dict(bs))
                elif not complete and not bs['complete']:
                    rv.append(self._row2dict(bs))
            else:
                rv.append(self._row2dict(bs))
        if resultSpec is not None:
            rv = self.applyResultSpec(rv, resultSpec)
        return defer.succeed(rv)

    @defer.inlineCallbacks
    def getRecentBuildsets(self, count=None, branch=None, repository=None,
                           complete=None):
        if not count:
            defer.returnValue([])
            return
        rv = []
        for bs in (yield self.getBuildsets(complete=complete)):
            if branch or repository:
                ok = True
                if not bs['sourcestamps']:
                    # no sourcestamps -> no match
                    ok = False
                for ssid in bs['sourcestamps']:
                    ss = yield self.db.sourcestamps.getSourceStamp(ssid)
                    if branch and ss['branch'] != branch:
                        ok = False
                    if repository and ss['repository'] != repository:
                        ok = False
            else:
                ok = True

            if ok:
                rv.append(bs)

        rv.sort(key=lambda bs: -bs['bsid'])

        defer.returnValue(list(reversed(rv[:count])))

    def _row2dict(self, row):
        row = row.copy()
        if row['complete_at']:
            row['complete_at'] = _mkdt(row['complete_at'])
        else:
            row['complete_at'] = None
        row['submitted_at'] = row['submitted_at'] and \
            _mkdt(row['submitted_at'])
        row['complete'] = bool(row['complete'])
        row['bsid'] = row['id']
        row['sourcestamps'] = self.buildset_sourcestamps.get(row['id'], [])
        del row['id']
        del row['properties']
        return row

    def getBuildsetProperties(self, key, no_cache=False):
        if key in self.buildsets:
            return defer.succeed(
                self.buildsets[key]['properties'])
        return defer.succeed({})

    # fake methods

    def fakeBuildsetCompletion(self, bsid, result):
        assert bsid in self.buildsets
        self.buildsets[bsid]['results'] = result
        self.completed_bsids.add(bsid)

    # assertions

    def assertBuildsetCompletion(self, bsid, complete):
        """Assert that the completion state of buildset BSID is COMPLETE"""
        actual = self.buildsets[bsid]['complete']
        self.t.assertTrue(
            (actual and complete) or (not actual and not complete))

    def assertBuildset(self, bsid=None, expected_buildset=None):
        """Assert that the given buildset looks as expected; the ssid parameter
        of the buildset is omitted.  Properties are converted with asList and
        sorted.  Attributes complete, complete_at, submitted_at, results, and parent_*
        are ignored if not specified."""
        self.t.assertIn(bsid, self.buildsets)
        buildset = self.buildsets[bsid].copy()
        del buildset['id']

        # clear out some columns if the caller doesn't care
        for col in 'complete complete_at submitted_at results parent_buildid parent_relationship'.split():
            if col not in expected_buildset:
                del buildset[col]

        if buildset['properties']:
            buildset['properties'] = sorted(buildset['properties'].items())

        self.t.assertEqual(buildset, expected_buildset)
        return bsid


class FakeWorkersComponent(FakeDBComponent):

    def setUp(self):
        self.workers = {}
        self.configured = {}
        self.connected = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Worker):
                self.workers[row.id] = dict(
                    id=row.id,
                    name=row.name,
                    info=row.info)
            elif isinstance(row, ConfiguredWorker):
                row.id = row.buildermasterid * 10000 + row.workerid
                self.configured[row.id] = dict(
                    buildermasterid=row.buildermasterid,
                    workerid=row.workerid)
            elif isinstance(row, ConnectedWorker):
                self.connected[row.id] = dict(
                    masterid=row.masterid,
                    workerid=row.workerid)

    def findWorkerId(self, name, _reactor=reactor):
        validation.verifyType(self.t, 'name', name,
                              validation.IdentifierValidator(50))
        for m in itervalues(self.workers):
            if m['name'] == name:
                return defer.succeed(m['id'])
        id = len(self.workers) + 1
        self.workers[id] = dict(
            id=id,
            name=name,
            info={})
        return defer.succeed(id)

    def _getWorkerByName(self, name):
        for worker in itervalues(self.workers):
            if worker['name'] == name:
                return worker
        return None

    def getWorker(self, workerid=None, name=None, masterid=None, builderid=None):
        # get the id and the worker
        if workerid is None:
            for worker in itervalues(self.workers):
                if worker['name'] == name:
                    workerid = worker['id']
                    break
            else:
                worker = None
        else:
            worker = self.workers.get(workerid)

        if not worker:
            return defer.succeed(None)

        # now get the connection status per builder_master, filtered
        # by builderid and masterid
        return defer.succeed(self._mkdict(worker, builderid, masterid))

    def getWorkers(self, masterid=None, builderid=None):
        if masterid is not None or builderid is not None:
            builder_masters = self.db.builders.builder_masters
            workers = []
            for worker in itervalues(self.workers):
                configured = [cfg for cfg in itervalues(self.configured)
                              if cfg['workerid'] == worker['id']]
                pairs = [builder_masters[cfg['buildermasterid']]
                         for cfg in configured]
                if builderid is not None and masterid is not None:
                    if (builderid, masterid) not in pairs:
                        continue
                if builderid is not None:
                    if not any(builderid == p[0] for p in pairs):
                        continue
                if masterid is not None:
                    if not any((masterid == p[1]) for p in pairs):
                        continue
                workers.append(worker)
        else:
            workers = list(itervalues(self.workers))

        return defer.succeed([
            self._mkdict(worker, builderid, masterid)
            for worker in workers])

    def workerConnected(self, workerid, masterid, workerinfo):
        worker = self.workers.get(workerid)
        # test serialization
        json.dumps(workerinfo)
        if worker is not None:
            worker['info'] = workerinfo
        new_conn = dict(masterid=masterid, workerid=workerid)
        if new_conn not in itervalues(self.connected):
            conn_id = max([0] + list(self.connected)) + 1
            self.connected[conn_id] = new_conn
        return defer.succeed(None)

    def deconfigureAllWorkersForMaster(self, masterid):
        buildermasterids = [_id for _id, (builderid, mid) in iteritems(self.db.builders.builder_masters)
                            if mid == masterid]
        for k, v in list(iteritems(self.configured)):
            if v['buildermasterid'] in buildermasterids:
                del self.configured[k]

    def workerConfigured(self, workerid, masterid, builderids):

        buildermasterids = [_id for _id, (builderid, mid) in iteritems(self.db.builders.builder_masters)
                            if mid == masterid and builderid in builderids]
        if len(buildermasterids) != len(builderids):
            raise ValueError("Some builders are not configured for this master: "
                             "builders: %s, master: %s buildermaster:%s" %
                             (builderids, masterid, self.db.builders.builder_masters))

        allbuildermasterids = [_id for _id, (builderid, mid) in iteritems(self.db.builders.builder_masters)
                               if mid == masterid]
        for k, v in list(iteritems(self.configured)):
            if v['buildermasterid'] in allbuildermasterids and v['workerid'] == workerid:
                del self.configured[k]
        self.insertTestData([ConfiguredWorker(workerid=workerid,
                                              buildermasterid=buildermasterid)
                             for buildermasterid in buildermasterids])
        return defer.succeed(None)

    def workerDisconnected(self, workerid, masterid):
        del_conn = dict(masterid=masterid, workerid=workerid)
        for id, conn in iteritems(self.connected):
            if conn == del_conn:
                del self.connected[id]
                break
        return defer.succeed(None)

    def _configuredOn(self, workerid, builderid=None, masterid=None):
        cfg = []
        for cs in itervalues(self.configured):
            if cs['workerid'] != workerid:
                continue
            bid, mid = self.db.builders.builder_masters[cs['buildermasterid']]
            if builderid is not None and bid != builderid:
                continue
            if masterid is not None and mid != masterid:
                continue
            cfg.append({'builderid': bid, 'masterid': mid})
        return cfg

    def _connectedTo(self, workerid, masterid=None):
        conns = []
        for cs in itervalues(self.connected):
            if cs['workerid'] != workerid:
                continue
            if masterid is not None and cs['masterid'] != masterid:
                continue
            conns.append(cs['masterid'])
        return conns

    def _mkdict(self, w, builderid, masterid):
        return {
            'id': w['id'],
            'workerinfo': w['info'],
            'name': w['name'],
            'configured_on': self._configuredOn(w['id'], builderid, masterid),
            'connected_to': self._connectedTo(w['id'], masterid),
        }


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
                assert row.objectid in list(itervalues(self.objects))
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
        except KeyError:
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

    def atomicCreateState(self, objectid, name, thd_create_callback):
        value = thd_create_callback()
        self.states[objectid][name] = json.dumps(bytes2NativeString(value))
        return defer.succeed(value)

    # fake methods

    def fakeState(self, name, class_name, **kwargs):
        id = self.objects[(name, class_name)] = self._newId()
        self.objects[(name, class_name)] = id
        self.states[id] = dict((k, json.dumps(v))
                               for k, v in iteritems(kwargs))
        return id

    # assertions

    def assertState(self, objectid, missing_keys=None, **kwargs):
        if missing_keys is None:
            missing_keys = []
        state = self.states[objectid]
        for k in missing_keys:
            self.t.assertFalse(k in state, "%s in %s" % (k, state))
        for k, v in iteritems(kwargs):
            self.t.assertIn(k, state)
            self.t.assertEqual(json.loads(state[k]), v,
                               "state is %r" % (state,))

    def assertStateByClass(self, name, class_name, **kwargs):
        objectid = self.objects[(name, class_name)]
        state = self.states[objectid]
        for k, v in iteritems(kwargs):
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
    @defer.inlineCallbacks
    def getBuildRequest(self, brid):
        row = self.reqs.get(brid)
        if row:
            claim_row = self.claims.get(brid, None)
            if claim_row:
                row.claimed_at = claim_row.claimed_at
                row.claimed = True
                row.masterid = claim_row.masterid
                row.claimed_by_masterid = claim_row.masterid
            else:
                row.claimed_at = None
            builder = yield self.db.builders.getBuilder(row.builderid)
            row.buildername = builder["name"]
            defer.returnValue(self._brdictFromRow(row))
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def getBuildRequests(self, builderid=None, complete=None, claimed=None,
                         bsid=None, branch=None, repository=None, resultSpec=None):
        rv = []
        for br in itervalues(self.reqs):
            if builderid and br.builderid != builderid:
                continue
            if complete is not None:
                if complete and not br.complete:
                    continue
                if not complete and br.complete:
                    continue
            claim_row = self.claims.get(br.id)
            if claim_row:
                br.claimed_at = claim_row.claimed_at
                br.claimed = True
                br.masterid = claim_row.masterid
                br.claimed_by_masterid = claim_row.masterid
            else:
                br.claimed_at = None
            if claimed is not None:
                if isinstance(claimed, bool):
                    if claimed:
                        if not claim_row:
                            continue
                    else:
                        if br.complete or claim_row:
                            continue
                else:
                    if not claim_row or claim_row.masterid != claimed:
                        continue
            if bsid is not None:
                if br.buildsetid != bsid:
                    continue

            if branch or repository:
                buildset = yield self.db.buildsets.getBuildset(br.buildsetid)
                sourcestamps = []
                for ssid in buildset['sourcestamps']:
                    sourcestamps.append((yield self.db.sourcestamps.getSourceStamp(ssid)))

                if branch and not any(branch == s['branch'] for s in sourcestamps):
                    continue
                if repository and not any(repository == s['repository'] for s in sourcestamps):
                    continue
            builder = yield self.db.builders.getBuilder(br.builderid)
            br.buildername = builder["name"]
            rv.append(self._brdictFromRow(br))
        if resultSpec is not None:
            rv = self.applyResultSpec(rv, resultSpec)
        defer.returnValue(rv)

    def claimBuildRequests(self, brids, claimed_at=None, _reactor=reactor):
        for brid in brids:
            if brid not in self.reqs or brid in self.claims:
                raise buildrequests.AlreadyClaimedError

        claimed_at = datetime2epoch(claimed_at)
        if not claimed_at:
            claimed_at = _reactor.seconds()

        # now that we've thrown any necessary exceptions, get started
        for brid in brids:
            self.claims[brid] = BuildRequestClaim(brid=brid,
                                                  masterid=self.MASTER_ID, claimed_at=claimed_at)
        return defer.succeed(None)

    def reclaimBuildRequests(self, brids, _reactor):
        for brid in brids:
            if brid in self.claims and self.claims[brid].masterid != self.db.master.masterid:
                raise buildrequests.AlreadyClaimedError

        # now that we've thrown any necessary exceptions, get started
        for brid in brids:
            self.claims[brid] = BuildRequestClaim(brid=brid,
                                                  masterid=self.MASTER_ID, claimed_at=_reactor.seconds())
        return defer.succeed(None)

    def unclaimBuildRequests(self, brids):
        for brid in brids:
            if brid in self.claims and self.claims[brid].masterid == self.db.master.masterid:
                self.claims.pop(brid)

    def completeBuildRequests(self, brids, results, complete_at=None,
                              _reactor=reactor):
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = _reactor.seconds()

        for brid in brids:
            if brid not in self.reqs or self.reqs[brid].complete == 1:
                raise buildrequests.NotClaimedError

        for brid in brids:
            self.reqs[brid].complete = 1
            self.reqs[brid].results = results
            self.reqs[brid].complete_at = complete_at
        return defer.succeed(None)

    def unclaimExpiredRequests(self, old, _reactor=reactor):
        old_epoch = _reactor.seconds() - old

        for br in itervalues(self.reqs):
            if br.complete == 1:
                continue

            claim_row = self.claims.get(br.id)
            if claim_row and claim_row.claimed_at < old_epoch:
                del self.claims[br.id]

    def _brdictFromRow(self, row):
        return buildrequests.BuildRequestsConnectorComponent._brdictFromRow(row, self.MASTER_ID)

    # fake methods

    def fakeClaimBuildRequest(self, brid, claimed_at=None, masterid=None):
        if masterid is None:
            masterid = self.MASTER_ID
        self.claims[brid] = BuildRequestClaim(brid=brid,
                                              masterid=masterid, claimed_at=self._reactor.seconds())

    def fakeUnclaimBuildRequest(self, brid):
        del self.claims[brid]

    # assertions

    def assertMyClaims(self, claimed_brids):
        self.t.assertEqual(
            [id for (id, brc) in iteritems(self.claims)
             if brc.masterid == self.MASTER_ID],
            claimed_brids)


class FakeBuildsComponent(FakeDBComponent):

    def setUp(self):
        self.builds = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Build):
                build = self.builds[row.id] = row.values.copy()
                build['properties'] = {}

        for row in rows:
            if isinstance(row, BuildProperty):
                assert row.buildid in self.builds
                self.builds[row.buildid]['properties'][
                    row.name] = (row.value, row.source)

    # component methods

    def _newId(self):
        id = 100
        while id in self.builds:
            id += 1
        return id

    def _row2dict(self, row):
        return dict(
            id=row['id'],
            number=row['number'],
            buildrequestid=row['buildrequestid'],
            builderid=row['builderid'],
            masterid=row['masterid'],
            workerid=row['workerid'],
            started_at=_mkdt(row['started_at']),
            complete_at=_mkdt(row['complete_at']),
            state_string=row['state_string'],
            results=row['results'])

    def getBuild(self, buildid):
        row = self.builds.get(buildid)
        if not row:
            return defer.succeed(None)

        return defer.succeed(self._row2dict(row))

    def getBuildByNumber(self, builderid, number):
        for row in itervalues(self.builds):
            if row['builderid'] == builderid and row['number'] == number:
                return defer.succeed(self._row2dict(row))
        return defer.succeed(None)

    def getBuilds(self, builderid=None, buildrequestid=None, workerid=None, complete=None, resultSpec=None):
        ret = []
        for (id, row) in iteritems(self.builds):
            if builderid is not None and row['builderid'] != builderid:
                continue
            if buildrequestid is not None and row['buildrequestid'] != buildrequestid:
                continue
            if workerid is not None and row['workerid'] != workerid:
                continue
            if complete is not None and complete != (row['complete_at'] is not None):
                continue
            ret.append(self._row2dict(row))
        if resultSpec is not None:
            ret = self.applyResultSpec(ret, resultSpec)
        return defer.succeed(ret)

    def addBuild(self, builderid, buildrequestid, workerid, masterid,
                 state_string, _reactor=reactor):
        validation.verifyType(self.t, 'state_string', state_string,
                              validation.StringValidator())
        id = self._newId()
        number = max([0] + [r['number'] for r in itervalues(self.builds)
                            if r['builderid'] == builderid]) + 1
        self.builds[id] = dict(id=id, number=number,
                               buildrequestid=buildrequestid, builderid=builderid,
                               workerid=workerid, masterid=masterid,
                               state_string=state_string,
                               started_at=_reactor.seconds(), complete_at=None,
                               results=None)
        return defer.succeed((id, number))

    def setBuildStateString(self, buildid, state_string):
        validation.verifyType(self.t, 'state_string', state_string,
                              validation.StringValidator())
        b = self.builds.get(buildid)
        if b:
            b['state_string'] = state_string
        return defer.succeed(None)

    def finishBuild(self, buildid, results, _reactor=reactor):
        now = _reactor.seconds()
        b = self.builds.get(buildid)
        if b:
            b['complete_at'] = now
            b['results'] = results
        return defer.succeed(None)

    def getBuildProperties(self, bid):
        if bid in self.builds:
            return defer.succeed(self.builds[bid]['properties'])
        return defer.succeed({})

    def setBuildProperty(self, bid, name, value, source):
        assert bid in self.builds
        self.builds[bid]['properties'][name] = (value, source)
        return defer.succeed(None)


class FakeStepsComponent(FakeDBComponent):

    def setUp(self):
        self.steps = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Step):
                self.steps[row.id] = row.values.copy()

    # component methods

    def _newId(self):
        id = 100
        while id in self.steps:
            id += 1
        return id

    def _row2dict(self, row):
        return dict(
            id=row['id'],
            buildid=row['buildid'],
            number=row['number'],
            name=row['name'],
            started_at=_mkdt(row['started_at']),
            complete_at=_mkdt(row['complete_at']),
            state_string=row['state_string'],
            results=row['results'],
            urls=json.loads(row['urls_json']),
            hidden=bool(row['hidden']))

    def getStep(self, stepid=None, buildid=None, number=None, name=None):
        if stepid is not None:
            row = self.steps.get(stepid)
            if not row:
                return defer.succeed(None)
            return defer.succeed(self._row2dict(row))
        else:
            if number is None and name is None:
                return defer.fail(RuntimeError("specify both name and number"))
            for row in itervalues(self.steps):
                if row['buildid'] != buildid:
                    continue
                if number is not None and row['number'] != number:
                    continue
                if name is not None and row['name'] != name:
                    continue
                return defer.succeed(self._row2dict(row))
            return defer.succeed(None)

    def getSteps(self, buildid):
        ret = []

        for row in itervalues(self.steps):
            if row['buildid'] != buildid:
                continue
            ret.append(self._row2dict(row))

        ret.sort(key=lambda r: r['number'])
        return defer.succeed(ret)

    def addStep(self, buildid, name, state_string, _reactor=reactor):
        validation.verifyType(self.t, 'state_string', state_string,
                              validation.StringValidator())
        validation.verifyType(self.t, 'name', name,
                              validation.IdentifierValidator(50))
        # get a unique name and number
        build_steps = [r for r in itervalues(self.steps)
                       if r['buildid'] == buildid]
        if build_steps:
            number = max([r['number'] for r in build_steps]) + 1
            names = set([r['name'] for r in build_steps])
            if name in names:
                i = 1
                while '%s_%d' % (name, i) in names:
                    i += 1
                name = '%s_%d' % (name, i)
        else:
            number = 0

        id = self._newId()
        self.steps[id] = {
            'id': id,
            'buildid': buildid,
            'number': number,
            'name': name,
            'started_at': None,
            'complete_at': None,
            'results': None,
            'state_string': state_string,
            'urls_json': '[]',
            'hidden': False}

        return defer.succeed((id, number, name))

    def startStep(self, stepid, _reactor=reactor):
        b = self.steps.get(stepid)
        if b:
            b['started_at'] = _reactor.seconds()
        return defer.succeed(None)

    def setStepStateString(self, stepid, state_string):
        validation.verifyType(self.t, 'state_string', state_string,
                              validation.StringValidator())
        b = self.steps.get(stepid)
        if b:
            b['state_string'] = state_string
        return defer.succeed(None)

    def addURL(self, stepid, name, url, _racehook=None):
        validation.verifyType(self.t, 'stepid', stepid,
                              validation.IntValidator())
        validation.verifyType(self.t, 'name', name,
                              validation.IdentifierValidator(50))
        validation.verifyType(self.t, 'url', url,
                              validation.StringValidator())
        b = self.steps.get(stepid)
        if b:
            urls = json.loads(b['urls_json'])
            urls.append(dict(name=name, url=url))
            b['urls_json'] = json.dumps(urls)
        return defer.succeed(None)

    def finishStep(self, stepid, results, hidden, _reactor=reactor):
        now = _reactor.seconds()
        b = self.steps.get(stepid)
        if b:
            b['complete_at'] = now
            b['results'] = results
            b['hidden'] = True if hidden else False
        return defer.succeed(None)


class FakeLogsComponent(FakeDBComponent):

    def setUp(self):
        self.logs = {}
        self.log_lines = {}  # { logid : [ lines ] }

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Log):
                self.logs[row.id] = row.values.copy()
        for row in rows:
            if isinstance(row, LogChunk):
                lines = self.log_lines.setdefault(row.logid, [])
                # make sure there are enough slots in the list
                if len(lines) < row.last_line + 1:
                    lines.append([None] * (row.last_line + 1 - len(lines)))
                row_lines = row.content.decode('utf-8').split('\n')
                lines[row.first_line:row.last_line + 1] = row_lines

    # component methods

    def _newId(self):
        id = 100
        while id in self.logs:
            id += 1
        return id

    def _row2dict(self, row):
        return dict(
            id=row['id'],
            stepid=row['stepid'],
            name=row['name'],
            slug=row['slug'],
            complete=bool(row['complete']),
            num_lines=row['num_lines'],
            type=row['type'])

    def getLog(self, logid):
        row = self.logs.get(logid)
        if not row:
            return defer.succeed(None)
        return defer.succeed(self._row2dict(row))

    def getLogBySlug(self, stepid, slug):
        row = None
        for row in itervalues(self.logs):
            if row['slug'] == slug and row['stepid'] == stepid:
                break
        else:
            return defer.succeed(None)
        return defer.succeed(self._row2dict(row))

    def getLogs(self, stepid=None):
        return defer.succeed([
            self._row2dict(row)
            for row in itervalues(self.logs)
            if row['stepid'] == stepid])

    def getLogLines(self, logid, first_line, last_line):
        if logid not in self.logs or first_line > last_line:
            return defer.succeed('')
        lines = self.log_lines.get(logid, [])
        rv = lines[first_line:last_line + 1]
        return defer.succeed(u'\n'.join(rv) + u'\n' if rv else u'')

    def addLog(self, stepid, name, slug, type):
        id = self._newId()
        self.logs[id] = dict(id=id, stepid=stepid,
                             name=name, slug=slug, type=type,
                             complete=0, num_lines=0)
        self.log_lines[id] = []
        return defer.succeed(id)

    def appendLog(self, logid, content):
        validation.verifyType(self.t, 'logid', logid,
                              validation.IntValidator())
        validation.verifyType(self.t, 'content', content,
                              validation.StringValidator())
        self.t.assertEqual(content[-1], u'\n')
        content = content[:-1].split('\n')
        lines = self.log_lines[logid]
        lines.extend(content)
        num_lines = self.logs[logid]['num_lines'] = len(lines)
        return defer.succeed((num_lines - len(content), num_lines - 1))

    def finishLog(self, logid):
        if id in self.logs:
            self.logs['id'].complete = 1
        return defer.succeed(None)

    def compressLog(self, logid, force=False):
        return defer.succeed(None)

    def deleteOldLogChunks(self, older_than_timestamp):
        # not implemented
        self._deleted = older_than_timestamp
        return defer.succeed(1)


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


class FakeMastersComponent(FakeDBComponent):

    data2db = {"masterid": "id", "link": "id"}

    def setUp(self):
        self.masters = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Master):
                self.masters[row.id] = dict(
                    id=row.id,
                    name=row.name,
                    active=bool(row.active),
                    last_active=_mkdt(row.last_active))

    def findMasterId(self, name, _reactor=reactor):
        for m in itervalues(self.masters):
            if m['name'] == name:
                return defer.succeed(m['id'])
        id = len(self.masters) + 1
        self.masters[id] = dict(
            id=id,
            name=name,
            active=False,
            last_active=_mkdt(_reactor.seconds()))
        return defer.succeed(id)

    def setMasterState(self, masterid, active, _reactor=reactor):
        if masterid in self.masters:
            was_active = self.masters[masterid]['active']
            self.masters[masterid]['active'] = active
            if active:
                self.masters[masterid]['last_active'] = \
                    _mkdt(_reactor.seconds())
            return defer.succeed(bool(was_active) != bool(active))
        else:
            return defer.succeed(False)

    def getMaster(self, masterid):
        if masterid in self.masters:
            return defer.succeed(self.masters[masterid])
        return defer.succeed(None)

    def getMasters(self):
        return defer.succeed(sorted(self.masters.values(),
                                    key=lambda x: x['id']))

    # test helpers

    def markMasterInactive(self, masterid):
        if masterid in self.masters:
            self.masters[masterid]['active'] = False
        return defer.succeed(None)


class FakeBuildersComponent(FakeDBComponent):

    def setUp(self):
        self.builders = {}
        self.builder_masters = {}
        self.builders_tags = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Builder):
                self.builders[row.id] = dict(
                    id=row.id,
                    name=row.name,
                    description=row.description)
            if isinstance(row, BuilderMaster):
                self.builder_masters[row.id] = \
                    (row.builderid, row.masterid)
            if isinstance(row, BuildersTags):
                assert row.builderid in self.builders
                self.builders_tags.setdefault(row.builderid,
                                              []).append(row.tagid)

    def findBuilderId(self, name, _reactor=reactor):
        for m in itervalues(self.builders):
            if m['name'] == name:
                return defer.succeed(m['id'])
        id = len(self.builders) + 1
        self.builders[id] = dict(
            id=id,
            name=name,
            description=None,
            tags=[])
        return defer.succeed(id)

    def addBuilderMaster(self, builderid=None, masterid=None):
        if (builderid, masterid) not in list(itervalues(self.builder_masters)):
            self.insertTestData([
                BuilderMaster(builderid=builderid, masterid=masterid),
            ])
        return defer.succeed(None)

    def removeBuilderMaster(self, builderid=None, masterid=None):
        for id, tup in iteritems(self.builder_masters):
            if tup == (builderid, masterid):
                del self.builder_masters[id]
                break
        return defer.succeed(None)

    def getBuilder(self, builderid):
        if builderid in self.builders:
            masterids = [bm[1] for bm in itervalues(self.builder_masters)
                         if bm[0] == builderid]
            bldr = self.builders[builderid].copy()
            bldr['masterids'] = sorted(masterids)
            return defer.succeed(self._row2dict(bldr))
        return defer.succeed(None)

    def getBuilders(self, masterid=None):
        rv = []
        for builderid, bldr in iteritems(self.builders):
            masterids = [bm[1] for bm in itervalues(self.builder_masters)
                         if bm[0] == builderid]
            bldr = bldr.copy()
            bldr['masterids'] = sorted(masterids)
            rv.append(self._row2dict(bldr))
        if masterid is not None:
            rv = [bd for bd in rv
                  if masterid in bd['masterids']]
        return defer.succeed(rv)

    def addTestBuilder(self, builderid, name=None):
        if name is None:
            name = "SomeBuilder-%d" % builderid
        self.db.insertTestData([
            Builder(id=builderid, name=name),
        ])

    @defer.inlineCallbacks
    def updateBuilderInfo(self, builderid, description, tags):
        if builderid in self.builders:
            tags = tags if tags else []
            self.builders[builderid]['description'] = description

            # add tags
            tagids = []
            for tag in tags:
                if not isinstance(tag, type(1)):
                    tag = yield self.db.tags.findTagId(tag)
                tagids.append(tag)
            self.builders_tags[builderid] = tagids

    def _row2dict(self, row):
        row = row.copy()
        row['tags'] = [self.db.tags.tags[tagid]['name']
                       for tagid in self.builders_tags.get(row['id'], [])]
        return row


class FakeTagsComponent(FakeDBComponent):

    def setUp(self):
        self.tags = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Tag):
                self.tags[row.id] = dict(
                    id=row.id,
                    name=row.name)

    def findTagId(self, name, _reactor=reactor):
        for m in itervalues(self.tags):
            if m['name'] == name:
                return defer.succeed(m['id'])
        id = len(self.tags) + 1
        self.tags[id] = dict(
            id=id,
            name=name)
        return defer.succeed(id)


class FakeDBConnector(service.AsyncMultiService):

    """
    A stand-in for C{master.db} that operates without an actual database
    backend.  This also implements a test-data interface similar to the
    L{buildbot.test.util.db.RealDatabaseMixin.insertTestData} method.

    The child classes implement various useful assertions and faking methods;
    see their documentation for more.
    """

    def __init__(self, testcase):
        service.AsyncMultiService.__init__(self)
        # reset the id generator, for stable id's
        Row._next_id = 1000
        self.t = testcase
        self.checkForeignKeys = False
        self._components = []
        self.changes = comp = FakeChangesComponent(self, testcase)
        self._components.append(comp)
        self.changesources = comp = FakeChangeSourcesComponent(self, testcase)
        self._components.append(comp)
        self.schedulers = comp = FakeSchedulersComponent(self, testcase)
        self._components.append(comp)
        self.sourcestamps = comp = FakeSourceStampsComponent(self, testcase)
        self._components.append(comp)
        self.buildsets = comp = FakeBuildsetsComponent(self, testcase)
        self._components.append(comp)
        self.workers = comp = FakeWorkersComponent(self, testcase)
        self._components.append(comp)
        self.state = comp = FakeStateComponent(self, testcase)
        self._components.append(comp)
        self.buildrequests = comp = FakeBuildRequestsComponent(self, testcase)
        self._components.append(comp)
        self.builds = comp = FakeBuildsComponent(self, testcase)
        self._components.append(comp)
        self.steps = comp = FakeStepsComponent(self, testcase)
        self._components.append(comp)
        self.logs = comp = FakeLogsComponent(self, testcase)
        self._components.append(comp)
        self.users = comp = FakeUsersComponent(self, testcase)
        self._components.append(comp)
        self.masters = comp = FakeMastersComponent(self, testcase)
        self._components.append(comp)
        self.builders = comp = FakeBuildersComponent(self, testcase)
        self._components.append(comp)
        self.tags = comp = FakeTagsComponent(self, testcase)
        self._components.append(comp)

    def setup(self):
        self.is_setup = True
        return defer.succeed(None)

    def insertTestData(self, rows):
        """Insert a list of Row instances into the database; this method can be
        called synchronously or asynchronously (it completes immediately) """
        for row in rows:
            if self.checkForeignKeys:
                row.checkForeignKeys(self, self.t)
            for comp in self._components:
                comp.insertTestData([row])
        return defer.succeed(None)


def _mkdt(epoch):
    # Local import for better encapsulation.
    from buildbot.util import epoch2datetime
    if epoch:
        return epoch2datetime(epoch)
