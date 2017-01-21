chsrc:HgPoller:'~buildbot.changes.hgpoller'
* Added the ability in a meta repository to detect changes in its sub repositories.
* Started updating the hgpoller and went through and updated the other code affected
as need
    * Updated the _processChanges function:
        1) Added steps to find if there were any differences in the .hgsubstate file in the meta-repository in the current changeset to any parent changeset.
        2) If there were any differences to add these changes using the self.master.data.updates.addChange function

data:Change:'~buildbot.data.changes'
    * Next, updated the following in the module:
        1) EntityType class - Added the new fields for recording the sub repo information: sub_repo_name, sub_repo_revision
        2) addChange function - Added the arguments for the sub repo information: sub_repo_name, sub_repo_revision
        3) self.master.config.preChangeGenerator calls - Added the arguments: sub_repo_name, sub_repo_revision
        4) self.master.db.changes.addChange call - Added the arguments: sub_repo_name, sub_repo_revision

buildbot:MasterConfig:'~buildbot.config'
    * Updated the call to the preChangeGenerator call with the new arguments:
        - sub_repo_name
        - sub_repo_revision

db:ChangesConnectorComponent:'~buildbot.db.changes
    * Updated the following:
        1) addChange function - new arguments: sub_repo_name, sub_repo_revision with the default value of None
        2) self.checkLength function call - added the new arguments: sub_repo_name, sub_repo_revision. Also, added these new arguments to the call for ch_tbl.c (which calls a column for a database table)
        3) thd function definition - Added the new arguments and new database columns: subreponame, subreporevision

db:Model:'~buildbot.db.model
    * Updated the following:
        1) Added the new columns to the changes table: subreponame, subreporevision
        2) Added the new database migration script to upgrade the database:
            048_adding_sub_repo_support.py
        in the /migrate/versions folder
