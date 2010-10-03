CREATE TABLE buildrequests (
    `id` INTEGER PRIMARY KEY AUTO_INCREMENT,

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
CREATE TABLE builds (
    `id` INTEGER PRIMARY KEY AUTO_INCREMENT,
    `number` INTEGER NOT NULL, -- BuilderStatus.getBuild(number)
    -- 'number' is scoped to both the local buildmaster and the buildername
    `brid` INTEGER NOT NULL, -- matches buildrequests.id
    `start_time` INTEGER NOT NULL,
    `finish_time` INTEGER
);
CREATE TABLE buildset_properties (
    `buildsetid` INTEGER NOT NULL,
    `property_name` VARCHAR(256) NOT NULL,
    `property_value` VARCHAR(1024) NOT NULL -- too short?
);
CREATE TABLE buildsets (
    `id` INTEGER PRIMARY KEY AUTO_INCREMENT,
    `external_idstring` VARCHAR(256),
    `reason` VARCHAR(256),
    `sourcestampid` INTEGER NOT NULL,
    `submitted_at` INTEGER NOT NULL,
    `complete` SMALLINT NOT NULL default 0,
    `complete_at` INTEGER,
    `results` SMALLINT -- 0=SUCCESS,2=FAILURE, from status/builder.py
     -- results is NULL until complete==1
);
CREATE TABLE change_files (
    `changeid` INTEGER NOT NULL,
    `filename` VARCHAR(1024) NOT NULL
);
CREATE TABLE change_links (
    `changeid` INTEGER NOT NULL,
    `link` VARCHAR(1024) NOT NULL
);
CREATE TABLE change_properties (
    `changeid` INTEGER NOT NULL,
    `property_name` VARCHAR(256) NOT NULL,
    `property_value` VARCHAR(1024) NOT NULL -- too short?
);
CREATE TABLE changes (
    `changeid` INTEGER PRIMARY KEY AUTO_INCREMENT, -- also serves as 'change number'
    `author` VARCHAR(1024) NOT NULL,
    `comments` VARCHAR(1024) NOT NULL, -- too short?
    `is_dir` SMALLINT NOT NULL, -- old, for CVS
    `branch` VARCHAR(1024) NULL,
    `revision` VARCHAR(256), -- CVS uses NULL. too short for darcs?
    `revlink` VARCHAR(256) NULL,
    `when_timestamp` INTEGER NOT NULL, -- copied from incoming Change
    `category` VARCHAR(256) NULL,

    -- repository specifies, along with revision and branch, the
    -- source tree in which this change was detected.
    `repository` text not null default '',

    -- project names the project this source code represents.  It is used
    -- later to filter changes
    `project` text not null default ''
);

CREATE TABLE patches (
    `id` INTEGER PRIMARY KEY AUTO_INCREMENT,
    `patchlevel` INTEGER NOT NULL,
    `patch_base64` TEXT NOT NULL, -- encoded bytestring
    `subdir` TEXT -- usually NULL
);
CREATE TABLE sourcestamp_changes (
    `sourcestampid` INTEGER NOT NULL,
    `changeid` INTEGER NOT NULL
);
CREATE TABLE sourcestamps (
    `id` INTEGER PRIMARY KEY AUTO_INCREMENT,
    `branch` VARCHAR(256) default NULL,
    `revision` VARCHAR(256) default NULL,
    `patchid` INTEGER default NULL,
    `repository` TEXT not null default '',
    `project` TEXT not null default ''
);

--
-- Scheduler Tables
--

-- This table records the "state" for each scheduler.  This state is, at least,
-- the last change that was analyzed, but is stored in an opaque JSON object.
-- Note that schedulers are never deleted.
CREATE TABLE schedulers (
    `schedulerid` INTEGER PRIMARY KEY AUTO_INCREMENT, -- joins to other tables
    `name` VARCHAR(128) NOT NULL, -- the scheduler's name according to master.cfg
    `class_name` VARCHAR(128) NOT NULL, -- the scheduler's class
    `state` VARCHAR(1024) NOT NULL -- JSON-encoded state dictionary
);
CREATE UNIQUE INDEX `name_and_class` ON schedulers (`name`, `class_name`);


-- This stores "classified" changes that have not yet been "processed".  That
-- is, the scheduler has looked at these changes and determined that something
-- should be done, but that hasn't happened yet.  Rows are "retired" from this
-- table as soon as the scheduler is done with the change.
CREATE TABLE scheduler_changes (
    `schedulerid` INTEGER,
    `changeid` INTEGER,
    `important` SMALLINT
);

-- This stores buildsets in which a particular scheduler is interested.
-- On every run, a scheduler checks its upstream buildsets for completion
-- and reacts accordingly.  Records are never deleted from this table, but
-- active is set to 0 when the record is no longer necessary.
CREATE TABLE scheduler_upstream_buildsets (
    `buildsetid` INTEGER,
    `schedulerid` INTEGER,
    `active` SMALLINT
);

--
-- Schema Information
--

-- database version; each upgrade script should change this
CREATE TABLE version (
    version INTEGER NOT NULL
);

CREATE INDEX `buildrequests_buildsetid` ON `buildrequests` (`buildsetid`);
CREATE INDEX `buildrequests_buildername` ON `buildrequests` (`buildername` (255));
CREATE INDEX `buildrequests_complete` ON `buildrequests` (`complete`);
CREATE INDEX `buildrequests_claimed_at` ON `buildrequests` (`claimed_at`);
CREATE INDEX `buildrequests_claimed_by_name` ON `buildrequests` (`claimed_by_name` (255));
CREATE INDEX `builds_number` ON `builds` (`number`);
CREATE INDEX `builds_brid` ON `builds` (`brid`);
CREATE INDEX `buildsets_complete` ON `buildsets` (`complete`);
CREATE INDEX `buildsets_submitted_at` ON `buildsets` (`submitted_at`);
CREATE INDEX `buildset_properties_buildsetid` ON `buildset_properties` (`buildsetid`);
CREATE INDEX `changes_branch` ON `changes` (`branch` (255));
CREATE INDEX `changes_revision` ON `changes` (`revision` (255));
CREATE INDEX `changes_author` ON `changes` (`author` (255));
CREATE INDEX `changes_category` ON `changes` (`category` (255));
CREATE INDEX `changes_when_timestamp` ON `changes` (`when_timestamp`);
CREATE INDEX `change_files_changeid` ON `change_files` (`changeid`);
CREATE INDEX `change_links_changeid` ON `change_links` (`changeid`);
CREATE INDEX `change_properties_changeid` ON `change_properties` (`changeid`);
CREATE INDEX `scheduler_changes_schedulerid` ON `scheduler_changes` (`schedulerid`);
CREATE INDEX `scheduler_changes_changeid` ON `scheduler_changes` (`changeid`);
CREATE INDEX `scheduler_upstream_buildsets_buildsetid` ON `scheduler_upstream_buildsets` (`buildsetid`);
CREATE INDEX `scheduler_upstream_buildsets_schedulerid` ON `scheduler_upstream_buildsets` (`schedulerid`);
CREATE INDEX `scheduler_upstream_buildsets_active` ON `scheduler_upstream_buildsets` (`active`);
CREATE INDEX `sourcestamp_changes_sourcestampid` ON `sourcestamp_changes` (`sourcestampid`);

INSERT INTO version VALUES(5);
