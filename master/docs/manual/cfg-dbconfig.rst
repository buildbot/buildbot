.. bb:cfg:: dbconfig

DbConfig
--------

DbConfig is an utility for master.cfg to get easy key/value storage in the buildbot database

DbConfig can get and store any jsonable object to the db for use by other masters or separate ui plugins to edit them.

The design is voluntary simplistic, the focus is on the easy use.

Example ::

    from buildbot.plugins import util, buildslave
    dbConfig = util.DbConfig(c['db']['db_url'], basedir)
    slaves = dbConfig.get("slaves")
    c['slaves'] = [
        buildslave.BuildSlave(slave['name'], slave['passwd'],
                              properties=slave.get('properties')),
        for slave in slaves
    ]
