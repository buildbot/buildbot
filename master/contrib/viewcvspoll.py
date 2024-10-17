#! /usr/bin/python


import os.path
import time

import MySQLdb  # @UnresolvedImport
from twisted.cred import credentials
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

"""Based on the fakechanges.py contrib script"""


class ViewCvsPoller:
    def __init__(self):
        def _load_rc():
            import user

            ret = {}
            for line in open(os.path.join(user.home, ".cvsblamerc")).readlines():
                if line.find("=") != -1:
                    key, val = line.split("=")
                    ret[key.strip()] = val.strip()
            return ret

        # maybe add your own keys here db=xxx, user=xxx, passwd=xxx
        self.cvsdb = MySQLdb.connect("cvs", **_load_rc())
        # self.last_checkin = "2005-05-11" # for testing
        self.last_checkin = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

    def get_changes(self):
        changes = []

        def empty_change():
            return {'who': None, 'files': [], 'comments': None}

        change = empty_change()

        cursor = self.cvsdb.cursor()
        cursor.execute(
            f"""SELECT whoid, descid, fileid, dirid, branchid, \
ci_when FROM checkins WHERE ci_when>='{self.last_checkin}'"""
        )
        last_checkin = None
        for whoid, descid, fileid, dirid, branchid, ci_when in cursor.fetchall():
            if branchid != 1:  # only head
                continue
            cursor.execute(f"""SELECT who from people where id={whoid}""")
            who = cursor.fetchone()[0]
            cursor.execute(f"""SELECT description from descs where id={descid}""")
            desc = cursor.fetchone()[0]
            cursor.execute(f"""SELECT file from files where id={fileid}""")
            filename = cursor.fetchone()[0]
            cursor.execute(f"""SELECT dir from dirs where id={dirid}""")
            dirname = cursor.fetchone()[0]
            if who == change["who"] and desc == change["comments"]:
                change["files"].append(f"{dirname}/{filename}")
            elif change["who"]:
                changes.append(change)
                change = empty_change()
            else:
                change["who"] = who
                change["files"].append(f"{dirname}/{filename}")
                change["comments"] = desc
            if last_checkin is None or ci_when > last_checkin:
                last_checkin = ci_when
        if last_checkin:
            self.last_checkin = last_checkin
        return changes


poller = ViewCvsPoller()


def error(*args):
    log.err()
    reactor.stop()


def poll_changes(remote):
    print("GET CHANGES SINCE", poller.last_checkin, end=' ')
    changes = poller.get_changes()
    for change in changes:
        print(change["who"], "\n *", "\n * ".join(change["files"]))
        change['src'] = 'cvs'
        remote.callRemote('addChange', change).addErrback(error)
    print()
    reactor.callLater(60, poll_changes, remote)


factory = pb.PBClientFactory()
reactor.connectTCP("localhost", 9999, factory)
deferred = factory.login(credentials.UsernamePassword("change", "changepw"))
deferred.addCallback(poll_changes).addErrback(error)

reactor.run()
