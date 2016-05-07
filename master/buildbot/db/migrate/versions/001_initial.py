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
import os

import sqlalchemy as sa
from future.utils import iteritems
from twisted.persisted import styles

from buildbot.db.migrate_utils import test_unicode
from buildbot.util import json
from buildbot.util import pickle
from buildbot.util import sautils

metadata = sa.MetaData()

last_access = sautils.Table(
    'last_access', metadata,
    sa.Column('who', sa.String(256), nullable=False),
    sa.Column('writing', sa.Integer, nullable=False),
    sa.Column('last_access', sa.Integer, nullable=False),
)

changes_nextid = sautils.Table(
    'changes_nextid', metadata,
    sa.Column('next_changeid', sa.Integer),
)

changes = sautils.Table(
    'changes', metadata,
    sa.Column('changeid', sa.Integer, autoincrement=False, primary_key=True),
    sa.Column('author', sa.String(256), nullable=False),
    sa.Column('comments', sa.String(1024), nullable=False),
    sa.Column('is_dir', sa.SmallInteger, nullable=False),
    sa.Column('branch', sa.String(256)),
    sa.Column('revision', sa.String(256)),
    sa.Column('revlink', sa.String(256)),
    sa.Column('when_timestamp', sa.Integer, nullable=False),
    sa.Column('category', sa.String(256)),
)

change_links = sautils.Table(
    'change_links', metadata,
    sa.Column('changeid', sa.Integer, sa.ForeignKey(
        'changes.changeid'), nullable=False),
    sa.Column('link', sa.String(1024), nullable=False),
)

change_files = sautils.Table(
    'change_files', metadata,
    sa.Column('changeid', sa.Integer, sa.ForeignKey(
        'changes.changeid'), nullable=False),
    sa.Column('filename', sa.String(1024), nullable=False),
)

change_properties = sautils.Table(
    'change_properties', metadata,
    sa.Column('changeid', sa.Integer, sa.ForeignKey(
        'changes.changeid'), nullable=False),
    sa.Column('property_name', sa.String(256), nullable=False),
    sa.Column('property_value', sa.String(1024), nullable=False),
)

schedulers = sautils.Table(
    "schedulers", metadata,
    sa.Column('schedulerid', sa.Integer,
              autoincrement=False, primary_key=True),
    sa.Column('name', sa.String(128), nullable=False),
    sa.Column('state', sa.String(1024), nullable=False),
)

scheduler_changes = sautils.Table(
    'scheduler_changes', metadata,
    sa.Column('schedulerid', sa.Integer,
              sa.ForeignKey('schedulers.schedulerid')),
    sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid')),
    sa.Column('important', sa.SmallInteger),
)

scheduler_upstream_buildsets = sautils.Table(
    'scheduler_upstream_buildsets', metadata,
    sa.Column('buildsetid', sa.Integer, sa.ForeignKey('buildsets.id')),
    sa.Column('schedulerid', sa.Integer,
              sa.ForeignKey('schedulers.schedulerid')),
    sa.Column('active', sa.SmallInteger),
)

sourcestamps = sautils.Table(
    'sourcestamps', metadata,
    sa.Column('id', sa.Integer, autoincrement=False, primary_key=True),
    sa.Column('branch', sa.String(256)),
    sa.Column('revision', sa.String(256)),
    sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
)

patches = sautils.Table(
    'patches', metadata,
    sa.Column('id', sa.Integer, autoincrement=False, primary_key=True),
    sa.Column('patchlevel', sa.Integer, nullable=False),
    sa.Column('patch_base64', sa.Text, nullable=False),
    sa.Column('subdir', sa.Text),
)

sourcestamp_changes = sautils.Table(
    'sourcestamp_changes', metadata,
    sa.Column('sourcestampid', sa.Integer, sa.ForeignKey(
        'sourcestamps.id'), nullable=False),
    sa.Column('changeid', sa.Integer, sa.ForeignKey(
        'changes.changeid'), nullable=False),
)

buildsets = sautils.Table(
    'buildsets', metadata,
    sa.Column('id', sa.Integer, autoincrement=False, primary_key=True),
    sa.Column('external_idstring', sa.String(256)),
    sa.Column('reason', sa.String(256)),
    sa.Column('sourcestampid', sa.Integer, sa.ForeignKey(
        'sourcestamps.id'), nullable=False),
    sa.Column('submitted_at', sa.Integer, nullable=False),
    sa.Column('complete', sa.SmallInteger, nullable=False,
              server_default=sa.DefaultClause("0")),
    sa.Column('complete_at', sa.Integer),
    sa.Column('results', sa.SmallInteger),
)

buildset_properties = sautils.Table(
    'buildset_properties', metadata,
    sa.Column('buildsetid', sa.Integer, sa.ForeignKey(
        'buildsets.id'), nullable=False),
    sa.Column('property_name', sa.String(256), nullable=False),
    sa.Column('property_value', sa.String(1024), nullable=False),
)

buildrequests = sautils.Table(
    'buildrequests', metadata,
    sa.Column('id', sa.Integer, autoincrement=False, primary_key=True),
    sa.Column('buildsetid', sa.Integer, sa.ForeignKey(
        "buildsets.id"), nullable=False),
    sa.Column('buildername', sa.String(length=256), nullable=False),
    sa.Column('priority', sa.Integer, nullable=False,
              server_default=sa.DefaultClause("0")),
    sa.Column('claimed_at', sa.Integer, server_default=sa.DefaultClause("0")),
    sa.Column('claimed_by_name', sa.String(length=256)),
    sa.Column('claimed_by_incarnation', sa.String(length=256)),
    sa.Column('complete', sa.Integer, server_default=sa.DefaultClause("0")),
    sa.Column('results', sa.SmallInteger),
    sa.Column('submitted_at', sa.Integer, nullable=False),
    sa.Column('complete_at', sa.Integer),
)

builds = sautils.Table(
    'builds', metadata,
    sa.Column('id', sa.Integer, autoincrement=False, primary_key=True),
    sa.Column('number', sa.Integer, nullable=False),
    sa.Column('brid', sa.Integer, sa.ForeignKey(
        'buildrequests.id'), nullable=False),
    sa.Column('start_time', sa.Integer, nullable=False),
    sa.Column('finish_time', sa.Integer),
)


def import_changes(migrate_engine):
    # get the basedir from the engine - see model.py if you're wondering
    # how it got there
    basedir = migrate_engine.buildbot_basedir

    # strip None from any of these values, just in case
    def remove_none(x):
        if x is None:
            return u""
        elif isinstance(x, str):
            return x.decode("utf8")
        else:
            return x

    # if we still have a changes.pck, then we need to migrate it
    changes_pickle = os.path.join(basedir, "changes.pck")
    if not os.path.exists(changes_pickle):
        migrate_engine.execute(changes_nextid.insert(),
                               next_changeid=1)
        return

    # if not quiet: print "migrating changes.pck to database"

    # 'source' will be an old b.c.changes.ChangeMaster instance, with a
    # .changes attribute.  Note that we use 'r', and not 'rb', because these
    # pickles were written using the old text pickle format, which requires
    # newline translation
    with open(changes_pickle, "r") as f:
        source = pickle.load(f)
    styles.doUpgrade()

    # if not quiet: print " (%d Change objects)" % len(source.changes)

    # first, scan for changes without a number.  If we find any, then we'll
    # renumber the changes sequentially
    have_unnumbered = False
    for c in source.changes:
        if c.revision and c.number is None:
            have_unnumbered = True
            break
    if have_unnumbered:
        n = 1
        for c in source.changes:
            if c.revision:
                c.number = n
                n = n + 1

    # insert the changes
    for c in source.changes:
        if not c.revision:
            continue
        try:
            values = dict(
                changeid=c.number,
                author=c.who,
                comments=c.comments,
                is_dir=0,
                branch=c.branch,
                revision=c.revision,
                revlink=c.revlink,
                when_timestamp=c.when,
                category=c.category)

            values = dict([(k, remove_none(v)) for k, v in iteritems(values)])
        except UnicodeDecodeError, e:
            raise UnicodeError(
                "Trying to import change data as UTF-8 failed.  Please look at contrib/fix_changes_pickle_encoding.py: %s" % str(e))

        migrate_engine.execute(changes.insert(), **values)

        # NOTE: change_links is not populated, since it is deleted in db
        # version 20.  The table is still created, though.

        # sometimes c.files contains nested lists -- why, I do not know!  But we deal with
        # it all the same - see bug #915. We'll assume for now that c.files contains *either*
        # lists of filenames or plain filenames, not both.
        def flatten(l):
            if l and isinstance(l[0], list):
                rv = []
                for e in l:
                    if isinstance(e, list):
                        rv.extend(e)
                    else:
                        rv.append(e)
                return rv
            else:
                return l
        for filename in flatten(c.files):
            migrate_engine.execute(change_files.insert(),
                                   changeid=c.number,
                                   filename=filename)

        for propname, propvalue in iteritems(c.properties.properties):
            encoded_value = json.dumps(propvalue)
            migrate_engine.execute(change_properties.insert(),
                                   changeid=c.number,
                                   property_name=propname,
                                   property_value=encoded_value)

    # update next_changeid
    max_changeid = max([c.number for c in source.changes if c.revision] + [0])
    migrate_engine.execute(changes_nextid.insert(),
                           next_changeid=max_changeid + 1)

    # if not quiet:
    # print "moving changes.pck to changes.pck.old; delete it or keep it as a
    # backup"
    os.rename(changes_pickle, changes_pickle + ".old")


def upgrade(migrate_engine):
    metadata.bind = migrate_engine

    # do some tests before getting started
    test_unicode(migrate_engine)

    # create the initial schema
    metadata.create_all()

    # and import some changes
    import_changes(migrate_engine)
