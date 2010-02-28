# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla-specific Buildbot steps.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Brian Warner <warner@lothar.com>
#   Chris AtLee <catlee@mozilla.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import sys, time, collections, base64, textwrap, os, cgi, re

try:
    import simplejson
    json = simplejson # this hushes pyflakes
except ImportError:
    import json

from twisted.python import log, reflect, threadable
from twisted.internet import defer, reactor
from twisted.enterprise import adbapi
from buildbot import util
from buildbot.util import collections as bbcollections
from buildbot.changes.changes import Change
from buildbot.sourcestamp import SourceStamp
from buildbot.buildrequest import BuildRequest
from buildbot.process.properties import Properties
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE
from buildbot.util.eventual import eventually

TABLES = [
    # the schema here is defined as version 1
    textwrap.dedent("""
        CREATE TABLE version (
            version INTEGER NOT NULL -- contains one row, currently set to 1
        );
    """),
    textwrap.dedent("""
        INSERT INTO version VALUES (1);
    """),

    # last_access is used for logging, to record the last time that each
    # client (or rather class of clients) touched the DB. The idea is that if
    # something gets weird, you can check this and discover that you have an
    # older tool (which uses a different schema) mucking things up.
    textwrap.dedent("""
        CREATE TABLE last_access (
            `who` VARCHAR(256) NOT NULL, -- like 'buildbot-0.8.0'
            `writing` INTEGER NOT NULL, -- 1 if you are writing, 0 if you are reading
            -- PRIMARY KEY (who, writing),
            `last_access` TIMESTAMP     -- seconds since epoch
        );
    """),

    textwrap.dedent("""
        CREATE TABLE changes_nextid (next_changeid INTEGER);
    """),
    textwrap.dedent("""
        INSERT INTO changes_nextid VALUES (1);
    """),

    textwrap.dedent("""
        -- Changes are immutable: once added, never changed
        CREATE TABLE changes (
            `changeid` INTEGER PRIMARY KEY NOT NULL, -- also serves as 'change number'
            `author` VARCHAR(1024) NOT NULL,
            `comments` VARCHAR(1024) NOT NULL, -- too short?
            `is_dir` SMALLINT NOT NULL, -- old, for CVS
            `branch` VARCHAR(1024) NULL,
            `revision` VARCHAR(256), -- CVS uses NULL. too short for darcs?
            `revlink` VARCHAR(256) NULL,
            `when_timestamp` INTEGER NOT NULL, -- copied from incoming Change
            `category` VARCHAR(256) NULL
        );
    """),

    textwrap.dedent("""
        CREATE TABLE change_links (
            `changeid` INTEGER NOT NULL,
            `link` VARCHAR(1024) NOT NULL
        );
    """),

    textwrap.dedent("""
        CREATE TABLE change_files (
            `changeid` INTEGER NOT NULL,
            `filename` VARCHAR(1024) NOT NULL
        );
    """),

    textwrap.dedent("""
        CREATE TABLE change_properties (
            `changeid` INTEGER NOT NULL,
            `property_name` VARCHAR(256) NOT NULL,
            `property_value` VARCHAR(1024) NOT NULL -- too short?
        );
    """),

    # Scheduler tables
    textwrap.dedent("""
        CREATE TABLE schedulers (
            `schedulerid` INTEGER PRIMARY KEY, -- joins to other tables
            `name` VARCHAR(256) UNIQUE NOT NULL,
            `state` VARCHAR(1024) NOT NULL -- JSON-encoded state dictionary
        );
    """),

    textwrap.dedent("""
        CREATE TABLE scheduler_changes (
            `schedulerid` INTEGER,
            `changeid` INTEGER,
            `important` SMALLINT
        );
    """),

    textwrap.dedent("""
        CREATE TABLE scheduler_upstream_buildsets (
            `buildsetid` INTEGER,
            `schedulerid` INTEGER,
            `active` SMALLINT
        );
    """),

    # SourceStamps
    textwrap.dedent("""
        -- SourceStamps are immutable: once added, never changed
        CREATE TABLE sourcestamps (
            `id` INTEGER PRIMARY KEY,
            `branch` VARCHAR(256) default NULL,
            `revision` VARCHAR(256) default NULL,
            `patchid` INTEGER default NULL
        );
    """),
    textwrap.dedent("""
        CREATE TABLE patches (
            `id` INTEGER PRIMARY KEY,
            `patchlevel` INTEGER NOT NULL,
            `patch_base64` TEXT NOT NULL, -- encoded bytestring
            `subdir` TEXT -- usually NULL
        );
    """),
    textwrap.dedent("""
        CREATE TABLE sourcestamp_changes (
            `sourcestampid` INTEGER NOT NULL,
            `changeid` INTEGER NOT NULL
        );
    """),

    # BuildRequests
    textwrap.dedent("""
        -- BuildSets are mutable. Python code may not cache them. Every
        -- BuildRequest must have exactly one associated BuildSet.
        CREATE TABLE buildsets (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `external_idstring` VARCHAR(256),
            `reason` VARCHAR(256),
            `sourcestampid` INTEGER NOT NULL,
            `submitted_at` INTEGER NOT NULL,
            `complete` SMALLINT NOT NULL default 0,
            `complete_at` INTEGER,
            `results` SMALLINT -- 0=SUCCESS,2=FAILURE, from status/builder.py
             -- results is NULL until complete==1
        );
    """),
    textwrap.dedent("""
        CREATE TABLE buildset_properties (
            `buildsetid` INTEGER NOT NULL,
            `property_name` VARCHAR(256) NOT NULL,
            `property_value` VARCHAR(1024) NOT NULL -- too short?
        );
    """),

    textwrap.dedent("""
        -- the buildrequests table represents the queue of builds that need to be
        -- done. In an idle buildbot, all requests will have complete=1.
        -- BuildRequests are mutable. Python code may not cache them.
        CREATE TABLE buildrequests (
            `id` INTEGER PRIMARY KEY NOT NULL,

            -- every BuildRequest has a BuildSet
            -- the sourcestampid and reason live in the BuildSet
            `buildsetid` INTEGER NOT NULL,

            `buildername` VARCHAR(256) NOT NULL,

            `priority` INTEGER NOT NULL default 0,

            -- claimed_at is the time at which a master most recently asserted that
            -- it is responsible for running the build: this will be updated
            -- periodically to maintain the claim
            `claimed_at` INTEGER default 0,

            -- claimed_by indicates which buildmaster has claimed this request. The
            -- 'name' contains hostname/basedir, and will be the same for subsequent
            -- runs of any given buildmaster. The 'incarnation' contains bootime/pid,
            -- and will be different for subsequent runs. This allows each buildmaster
            -- to distinguish their current claims, their old claims, and the claims
            -- of other buildmasters, to treat them each appropriately.
            `claimed_by_name` VARCHAR(256) default NULL,
            `claimed_by_incarnation` VARCHAR(256) default NULL,

            `complete` INTEGER default 0, -- complete=0 means 'pending'

             -- results is only valid when complete==1
            `results` SMALLINT, -- 0=SUCCESS,1=WARNINGS,etc, from status/builder.py

            `submitted_at` INTEGER NOT NULL,

            `complete_at` INTEGER
        );
    """),

    textwrap.dedent("""
        -- this records which builds have been started for each request
        CREATE TABLE builds (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `number` INTEGER NOT NULL, -- BuilderStatus.getBuild(number)
            -- 'number' is scoped to both the local buildmaster and the buildername
            `brid` INTEGER NOT NULL, -- matches buildrequests.id
            `start_time` INTEGER NOT NULL,
            `finish_time` INTEGER
        );
    """),

    ]
