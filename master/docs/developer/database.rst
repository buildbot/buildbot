The Buildbot Database
=====================

Database Schema
~~~~~~~~~~~~~~~

.. py:class:: buildbot.db.schema.DBSchemaManager

The SQL for the database schema is available in
:file:`buildbot/db/schema/tables.sql`.  However, note that this file is not used
for new installations or upgrades of the Buildbot database.

Instead, the :class:`buildbot.db.schema.DBSchemaManager` handles this task.  The
operation of this class centers around a linear sequence of database versions.
Versions start at 0, which is the old pickle-file format.  The manager has
methods to query the version of the database, and the current version from the
source code.  It also has an :meth:`upgrade` method which will upgrade the
database to the latest version.  This operation is currently irreversible.

There is no operation to "install" the latest schema.  Instead, a fresh install
of buildbot begins with an (empty) version-0 database, and upgrades to the
current version.  This trades a bit of efficiency at install time for
assurances that the upgrade code is well-tested.

Changing the Schema
~~~~~~~~~~~~~~~~~~~

To make a change to the database schema, follow these steps:

 1. Increment ``CURRENT_VERSION`` in :file:`buildbot/db/schema/manager.py` by
     one.  This is your new version number.

 2. Create :file:`buildbot/db/schema/v{N}.py`, where *N* is your version number, by
    copying the previous script and stripping it down.  This script should define a
    subclass of :class:`buildbot.db.schema.base.Updater` named ``Updater``. 
    
    The class must define the method :meth:`upgrade`, which takes no arguments.  It
    should upgrade the database from the previous version to your version,
    including incrementing the number in the ``VERSION`` table, probably with an
    ``UPDATE`` query.
    
    Consult the API documentation for the base class for information on the
    attributes that are available.

 3. Edit :file:`buildbot/test/unit/test_db_schema_master.py`.  If your upgrade
    involves moving data from the basedir into the database proper, then edit
    :meth:`fill_basedir` to add some test data.
    
    Add code to :meth:`assertDatabaseOKEmpty` to check that your upgrade works on an
    empty database.
    
    Add code to :meth:`assertDatabaseOKFull` to check that your upgrade works on a
    database with pre-existing data.  Do this even if your changes do not move any
    data from the basedir.
    
    Run the tests to find the bugs you introduced in step 2.

 4. Increment the version number in the ``test_get_current_version`` test in the
    same file.  Only do this after you've finished the previous step - a failure of
    this test is a good reminder that testing isn't done yet.


 5. Updated the version number in :file:`buildbot/db/schema/tables.sql`, too.

 6. Finally, make the corresponding changes to :file:`buildbot/db/schema/tables.sql`.


