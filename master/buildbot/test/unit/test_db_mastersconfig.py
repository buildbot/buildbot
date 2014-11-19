from twisted.trial import unittest
from twisted.internet import defer, task
from buildbot.db import mastersconfig
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb
from buildbot.util import epoch2datetime


class TestMastersConfigConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):


    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['mastersconfig', 'objects',
                         'buildrequest_claims', 'buildrequests'])

        def finish_setup(_):
            self.db.mastersconfig = mastersconfig.MastersConfigConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # common sample data

    background_data = [
        fakedb.Object(id=1, name='katana/buildmaster-01', class_name='buildbot.master.BuildMaster'),
        fakedb.Object(id=2, name='katana/buildmaster-02', class_name='buildbot.master.BuildMaster'),
        fakedb.MasterConfig(id=1, buildbotURL='http://localhost:8001/', objectid=1),
        fakedb.MasterConfig(id=2, buildbotURL='http://localhost:8002/', objectid=2),
        fakedb.BuildRequest(id=1, buildsetid=1, buildername='b1'),
        fakedb.BuildRequest(id=2, buildsetid=2, buildername='b1'),
        fakedb.BuildRequestClaim(brid=1, objectid=1, claimed_at='1416383733'),
        fakedb.BuildRequestClaim(brid=2, objectid=2, claimed_at='1416383733'),
    ]

    def test_setupMaster(self):
        d = self.db.mastersconfig.setupMaster('http://localhost:8001/', 1)
        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.mastersconfig.select())
                rows = [(row.id, row.buildbotURL, row.objectid)
                         for row in r.fetchall()]
                self.assertEqual(rows,
                    [(1, 'http://localhost:8001/', 1)])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_getMasterURL(self):
        d = self.insertTestData(self.background_data)

        def check(row, expected_master={}):
            self.assertEqual(row, expected_master)

        d.addCallback(lambda _ : self.db.mastersconfig.getMasterURL(1))
        d.addCallback(check, expected_master={'buildbotURL': 'http://localhost:8001/',
                                              'id': 1, 'objectid': 1})
        d.addCallback(lambda _ : self.db.mastersconfig.getMasterURL(2))
        d.addCallback(check, expected_master={'buildbotURL': 'http://localhost:8002/',
                                              'id': 2, 'objectid': 2})

        return d