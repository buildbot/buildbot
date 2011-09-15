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
#
# inspirated, and some code from:
#    :copyright: (c) 2011 by the Werkzeug Team, see Werkzeug's AUTHORS for more details.

try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1
from time import time
from datetime import *
from random import random
import os
from twisted.internet import defer
def _urandom():
    if hasattr(os, 'urandom'):
        return os.urandom(30)
    return random()

def generate_cookie():
    return sha1('%s%s' % (time(), _urandom())).hexdigest()


class Session():
    """I'm a user's session. Contains information about a user's session
    a user can have several session
    a session is associated with a cookie
    """
    user = ""
    infos = {}
    def __init__(self, user, infos):
        self.user = user
        self.infos = infos
        self.renew()
    def renew(self):
        # one day expiration. hardcoded for now...
        self.expiration = datetime.now()+ timedelta(1)
        return self.expiration
    def expired(self):
        return datetime.now() > self.expiration
    def userInfosHTML(self):
        return '%(fullName)s[<a href="mailto:%(email)s">%(email)s</a>]'%(self.infos)
    def getExpiration(self):
        delim = '-'
        d = self.expiration.utctimetuple()
        return '%s, %02d%s%s%s%s %02d:%02d:%02d GMT' % (
            ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')[d.tm_wday],
            d.tm_mday, delim,
            ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
             'Oct', 'Nov', 'Dec')[d.tm_mon - 1],
            delim, str(d.tm_year), d.tm_hour, d.tm_min, d.tm_sec
            )

class SessionManager():
    """I'm the session manager. Holding the current sessions
    managing cookies, and their expiration

    KISS version for the moment
    The sessions are stored in RAM so that you have to relogin after buildbot reboot
    old sessions are searched at every connection, which is not very good for scaling
    """
    def __init__(self):
        self.sessions = {} # cookie indexed dictionary of Session()
        
    def new(self, user, infos):
        cookie = generate_cookie()
        self.sessions[cookie] = s = Session(user, infos)
        return cookie, s
    def gc(self):
        """remove old cookies"""
        for cookie in self.sessions:
            s =  self.sessions[cookie]
            if s.expired():
                del self.sessions[cookie]
    def get(self, cookie):
        self.gc()
        if cookie in self.sessions:
            return  self.sessions[cookie]
        return None
    def remove(self, cookie):
        if cookie in self.sessions:
            del self.sessions[cookie]
