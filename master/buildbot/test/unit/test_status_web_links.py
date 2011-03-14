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

import buildbot.status.web.base as wb
import jinja2, re

from twisted.trial import unittest

class RevisionLinks(unittest.TestCase):
    """
    Test webstatus revision link filters
    """

    def setUp(self):
        pass
    
    def _test(self, env, should_have_links=True):
        for name in ['shortrev', 'revlink']:
            f = env.filters[name]
            for r in [None, 'repo', 'repo2', 'sub/repo']:    
                self.assertNotSubstring('<a', f(None, r), 'repo: %s' % r)
                if should_have_links: 
                    self.assertSubstring('<a', f(1234, r), 'repo: %s' % r) 
                    self.assertSubstring('<a', f('deadbeef1234', r), 'repo: %s' % r) 
                else:
                    self.assertNotSubstring('<a', f(1234, r), 'repo: %s' % r) 
                    self.assertNotSubstring('<a', f('deadbeef1234', r), 'repo: %s' % r) 
        
    def test_default(self):
        env = wb.createJinjaEnv()
        self._test(env, False)
        
    def test_format(self):
        env = wb.createJinjaEnv('http://myserver.net/repo/%s')
        self._test(env)

    def test_dict(self):
        env = wb.createJinjaEnv({None: 'http://default.net/repo/%s',
                                 'repo': 'http://myserver.net/repo/%s',
                                 'repo2': 'http://myserver2.net/repo/%s',
                                 'sub/repo': 'http://otherserver.com/%s'})
        self._test(env)

    def test_callable(self):
        def my_revlink(rev, repo):
            import urllib
            if not rev:
                return None
            if not repo:
                repo = 'main'
            rev = urllib.quote(rev)
            repo = urllib.quote(repo)
            return 'http://myserver.net/repos/%s/rev/%s' % (repo, rev)
        
        env = wb.createJinjaEnv(my_revlink)
        self._test(env)


    def test_template(self):
        template_str = '''{{ rev|revlink('repo') }} - {{ rev|shortrev('repo') }}'''
        env = wb.createJinjaEnv(revlink='http://myserver.net/repo/%s')
        template = env.from_string(template_str)
        
        rev = '1234567890' * 4 # reasonably long
        html = template.render(rev=rev)
        self.assertSubstring('http://myserver.net/repo/%s' % rev, html)
        self.assertSubstring('...', html) # did it get shortened?
        self.assertEquals(html.count('<a'), 3) # one in revlink, two in shortrev
    

class ChangeCommentLinks(unittest.TestCase):
    """
    Tests webstatus changecomment link filter
    """

    def setUp(self):
        pass
    
    def _test(self, env):
        f = env.filters['changecomment']
        for p in [None, 'project1', 'project2']:
            self.assertNotSubstring('<a', f('', p)) 
            self.assertNotSubstring('<a', f('There is no ticket...', p)) 
            self.assertSubstring('<a', f('There is a ticket #123', p)) 
            self.assertEquals(f('There are two tickets #123 and #456', p).count("<a"), 2) 
                
        
    def test_default(self):
        env = wb.createJinjaEnv()
        f = env.filters['changecomment']
        self.assertNotSubstring('<a', f(None, '')) 
        self.assertNotSubstring('<a', f(None, 'There is no ticket #123')) 
        self.assertNotSubstring('<a', f('project', '')) 
        self.assertNotSubstring('<a', f('project', 'There is no ticket #123')) 

    def test_tuple2(self):
        env = wb.createJinjaEnv(
            changecommentlink=(r'#(\d+)', r'http://buildbot.net/trac/ticket/\1')) 
        self._test(env)

    def test_tuple3(self):
        env = wb.createJinjaEnv(
            changecommentlink=(r'#(\d+)', r'http://buildbot.net/trac/ticket/\1',
                               r'Ticket #\1')) 
        self._test(env)

    def test_dict_2tuple(self):
        env = wb.createJinjaEnv(
            changecommentlink={
               None: (r'#(\d+)', r'http://server/trac/ticket/\1'), 
               'project1': (r'#(\d+)', r'http://server/trac/p1/ticket/\1'), 
               'project2': (r'#(\d+)', r'http://server/trac/p2/ticket/\1') 
            })
        self._test(env)        
        
        f = env.filters['changecomment']
        self.assertNotSubstring('<a', f('fixed #123', 'nonexistingproject')) 


    def test_dict_3tuple(self):
        env = wb.createJinjaEnv(
            changecommentlink={
               None: (r'#(\d+)', r'http://server/trac/ticket/\1', r'Ticket #\1'), 
               'project1': (r'#(\d+)', r'http://server/trac/p1/ticket/\1', r'Ticket #\1'), 
               'project2': (r'#(\d+)', r'http://server/bugzilla/p2/ticket/\1', r'Bug #\1') 
            })
        self._test(env)        

        f = env.filters['changecomment']
        self.assertNotSubstring('<a', f('fixed #123', 'nonexistingproject')) 

    def test_callable(self):
        r1 = re.compile(r'#(\d+)') 
        r2 = re.compile(r'bug ([a-eA-E0-9]+)')

        r1_sub = jinja2.Markup(r'<a href="\1" title="Ticket #\1">\g<0></a>')
        r2_sub = jinja2.Markup(r'<a href="\1" title="Bug \1"><img src="\bug.png">\g<0></a>')
               
        def my_changelink(changehtml, project):
            if project == 'nonexistingproject':
                return changehtml
            
            html1 = r1.sub(r1_sub, changehtml)
            html2 = r2.sub(r2_sub, html1)    
            return html2

        env = wb.createJinjaEnv(changecommentlink=my_changelink)
        self._test(env)
        
        f = env.filters['changecomment']        
        self.assertNotSubstring('<a', f('fixed #123', 'nonexistingproject')) 

    
class DictLinkfilter(unittest.TestCase):
    '''test the dictlink filter used for top-level links to 
       projects and repostiories'''
    
    def test_default(self):
        f = wb.dictlinkfilter(None) 
        
        self.assertNotSubstring('<a', f(None))
        self.assertNotSubstring('<a', f('repo'))
        self.assertNotSubstring('<a', f('repo2'))
         
    def test_simple(self):
        f = wb.dictlinkfilter({'repo': 'http://myrepo.net'})
        
        self.assertNotSubstring('<a', f(None))
        self.assertSubstring('<a', f('repo'))
        self.assertNotSubstring('<a', f('repo2'))
        self.assertEquals(f('bah'), 'bah') # passthrough
        
    def test_callable(self):
        def my_dictlink(value):
            if len(value) == 0:
                return 'http://thevoid.net'
            if len(value) == 1:
                return 'http://highlander.net'
            if value == 'hiddenproject':
                return None
            else:
                return 'http://legion.net'
            
        f = wb.dictlinkfilter(my_dictlink)
        self.assertSubstring('thevoid', f(''))
        self.assertSubstring('highlander', f('X'))
        self.assertSubstring('legion', f('many'))
        self.assertSubstring('<a', f('many'))
        self.assertNotSubstring('<a', f('hiddenproject'))
        
        
    def test_jinjaenv(self):
        env = wb.createJinjaEnv(repositories={'a': 'http://a.net'},
                                projects={'b': 'http://b.net'})
        
        self.assertSubstring('<a href="http://a.net">', env.filters['repolink']('a'))
        self.assertSubstring('<a href="http://b.net">', env.filters['projectlink']('b'))
        
        
class EmailFilter(unittest.TestCase):
    ''' test that the email filter actually obfuscates email addresses'''

    def test_emailfilter(self):
        self.assertNotSubstring('me@the.net', wb.emailfilter('me@the.net'))
        self.assertSubstring('me', wb.emailfilter('me@the.net'))
        self.assertSubstring('@', wb.emailfilter('me@the.net'))
        self.assertSubstring('the.net', wb.emailfilter('me@the.net'))
        
        
        
class UserFilter(unittest.TestCase):
    '''test commit user names filtering, should be safe from complete
        email addresses and split user/email into separate HTML instances'''
    
    def test_emailfilter(self):
        self.assertNotSubstring('me@the.net', wb.userfilter('me@the.net'))
        self.assertNotSubstring('me@the.net', wb.userfilter('Me <me@the.net>'))
        
    def test_emailfilter_split(self):
        self.assertNotSubstring('Me <me', wb.userfilter('Me <me@the.net>'))
        self.assertSubstring('me', wb.userfilter('Me <me@the.net>'))
        self.assertSubstring('the.net', wb.userfilter('Me <me@the.net>'))
        self.assertSubstring('John Doe', wb.userfilter('John Doe <me@the.net>'))
        
        
        
        
