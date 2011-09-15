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

from twisted.internet import defer
from twisted.python import log
from twisted.protocols import basic

from zope.interface import Interface, Attribute, implements
import email

from buildbot import pbutil
from buildbot.util.maildir import MaildirService
from buildbot.util import netstrings
from buildbot.process.properties import Properties
from buildbot.schedulers import base
from buildbot.status.buildset import BuildSetStatus
import re

class IParameter(Interface):
    """Represent a forced build parameter"""
    name = Attribute("name","name of the underlying property, and form field")
    label = Attribute("label","label displayed in form. default will be name")
    type = Attribute("type", "type of widget in form")
    default = Attribute("default", "default string value, if nothing is provided in form will still fo through validation")
    required = Attribute("required", "if True, buildbot will ensure a valid value in this field")
    def parse_from_post(self, s):
        """return python object from POST http request's parameter
           raise ValueError if passed string is no valid
        """

class BaseParameter:
    implements(IParameter)
    name = ""
    label = ""
    type = ""
    default = ""
    required = False
    def __init__(self, name, label=None, **kw):
        self.label = self.name = name
        if label:
            self.label = label
        # all other properties are generically passed via **kw
        self.__dict__.update(kw)
    def parse_from_post(self, s):
        return s

class FixedParameter(BaseParameter):
    """A forced build parameter, that always has a fixed value
       and does not show up in the web form, or is just shown as readonly
    """
    type = "fixed"
    hide = True
    default = ""
class StringParameter(BaseParameter):
    """Represent a string forced build parameter
       regular expression validation is optionally done
    """
    regex = None
    type = "text"
    size = 10 # size of the input field
    def __init__(self, name=None, label=None, regex=None, **kw):
        BaseParameter.__init__(self, name, label, **kw)
        if regex:
            self.regex = re.compile(regex)
    def parse_from_post(self, s):
        if self.regex:
            if not self.regex.match(s):
                raise ValueError("%s:'%s' does not match pattern '%s'"%(self.label, s, self.regex.pattern))
        return s

class TextParameter(StringParameter):
    """Represent a string forced build parameter
       regular expression validation is optionally done
       it is represented by a textarea
       extra parameter cols, and rows are available to the template system

       this can be subclassed in order to have more customization
       e.g. developer could send a list of git branch to pull from
       	    developer could send a list of gerrit changes to cherry-pick, etc
            developer could send a shell script to amend the build.
       beware of security issues anyway.
    """
    type = "textarea"
    cols = 80
    """the number of columns textarea will have"""
    rows = 20
    """the number of rows textarea will have"""

class IntParameter(StringParameter):
    """Represent an integer forced build parameter"""
    type = "int"
    parse_from_post = int # will thrown exception if parse fail

class BooleanParameter(BaseParameter):
    """Represent a boolean forced build parameter
       will be presented as a checkbox
    """
    type = "bool"
    parse_from_post = bool # will thrown exception if parse fail

class UserNameParameter(StringParameter):
    """Represent a username in the form "User <email@email.com>" """
    type = "text"
    default = ""
    size = 30
    need_email = True
    def __init__(self, name="username", label="Your name:", **kw):
        BaseParameter.__init__(self, name, label, **kw)
    def parse_from_post(self, s):
        if self.need_email:
            e = email.utils.parseaddr(s)
            if e == ('',''):
                raise ValueError("%s: please fill in email address"%(self.label))
        return s

class ChoiceStringParameter(BaseParameter):
    """Represent build parameter with a list of choices"""
    type = "list"
    choices = []
    """ the list of choices """
    strict = True
    """ the parameter is enforcing only values in choices list is passed"""
    def parse_from_post(self, s):
        if self.strict and not s in self.choices:
            raise ValueError("'%s' does not belongs to list of available choices '%s'"%(s, self.choices))
        return s

class AnyPropertyParameter(BaseParameter):
    """a property for setting arbitrary property in the build
    a bit atypical, as it will generate two fields in the html form
    """
    type = "anyproperty"
    

class ForceSched(base.BaseScheduler):
    
    compare_attrs = ( 'name', 'builderNames', 'branch', 'reason', 'revision','repository','project', 'properties' )

    def __init__(self, name, builderNames, branch=StringParameter(name="branch",default=""), 
                       	     		   reason=StringParameter(name="reason", default="force build"),
                 			   revision=StringParameter(name="revision",default=""),
                 			   repository=StringParameter(name="repository",default=""),
                 			   project=StringParameter(name="repository",default=""),
                 			   username=UserNameParameter(),
                 			   properties=[AnyPropertyParameter("property1"),
                                                       AnyPropertyParameter("property2"),
                                                       AnyPropertyParameter("property3"),
                                                       AnyPropertyParameter("property4")
                                                       ]):
        """This scheduler is a bit similar to the TrySched, for access via web interface, and json interface (@todo)
           having a very clean and elegant interface make it difficult keep backward config compatibility, so we do a new Sched type.
           """
        base.BaseScheduler.__init__(self, name=name, builderNames=builderNames,properties={})
        self.branch = branch
        self.reason = reason
        self.repository = repository
        self.revision = revision
        self.project = project
        self.username = username
        self.properties = properties
        # this is used to simplify the template
        self.all_fields = [ branch, username, reason, repository,revision, project ]
        self.all_fields.extend(properties)

    def startService(self):
        pass

    def stopService(self):
        pass

    def forceWithJSONRequest(self, owner, req):
        pass # todo
    @defer.deferredGenerator
    def forceWithWebRequest(self, owner, builder_name, req):
        """Called by the web UI.
        Authentication is already done, thus owner is passed as argument
        We check the parameters, and launch the build, if everything is correct
        """
        if not builder_name in self.builderNames:
            # silently fail in case of buildAll, on a non supported builder
            return 
        master = self.master
        properties = {}
        # probably need to clean that out later as the IProperty is already a validation
        # mechanism
        validation = master.config.validation
        pname_validate = validation['property_name']
        pval_validate = validation['property_value']
        additionnal_validate = {}
        additionnal_validate[self.branch.name] =  validation['branch']
        additionnal_validate[self.revision.name] =  validation['revision']

        # validation stuff, put everything into properties dictionary
        for param in self.all_fields:
            if owner and param==self.username:
                continue # dont enforce username if auth
            if isinstance(param, AnyPropertyParameter):
                pname = req.args.get("%sname" % param.name, [""])[0]
                pvalue = req.args.get("%svalue" % param.name, [""])[0]
                if not pname:
                    break
                if not pname_validate.match(pname) \
                        or not pval_validate.match(pvalue):
                    raise ValueError("bad property name='%s', value='%s'" % (pname, pvalue))
            elif isinstance(param, BooleanParameter):
                # damn html's ungeneric checkbox implementation...
                checkbox = req.args.get("checkbox", [""])
                properties[param.name] = param.name in checkbox
            else:
                arg = req.args.get(param.name, [""])[0]
                if arg == "":
                    if param.required:
                        raise ValueError("'%s' needs to be specified" % (param.label))
                    arg = param.default
                if param.name in additionnal_validate:
                    if not additionnal_validate[param.name].match(arg):
                        raise ValueError("bad %s: value='%s'" % (param.label, arg))
                arg = param.parse_from_post(arg)
                if arg == None:
                    raise ValueError("need %s: no default provided by config"%(param.name))
                properties[param.name] = arg

        # everything is validated, we can create our source stamp, and buildrequest
        reason = properties[self.reason.name]
        branch = properties[self.branch.name]
        revision = properties[self.revision.name]
        repository = properties[self.repository.name]
        project = properties[self.project.name]
        if owner is None:
            owner =  properties[self.username.name]

        std_prop_names = [self.branch.name, 
                          self.revision.name, self.repository.name,
                          self.project.name, self.username.name]
        real_properties = Properties()
        for pname, pvalue in properties.items():
            if not pname in std_prop_names:
                real_properties.setProperty(pname, pvalue, "Force Build Form")

        real_properties.setProperty("owner", owner, "Force Build Form")
        d = master.db.sourcestamps.addSourceStamp(branch=branch,
                revision=revision, project=project, repository=repository)

        wfd = defer.waitForDeferred(d)
        yield wfd
        ssid = wfd.getResult()

        r = ("The web-page 'force build' button was pressed by '%s': %s\n"
             % (owner, reason)) 
        d = master.addBuildset(builderNames=[builder_name],
                               ssid=ssid, reason=r,
                               properties=real_properties.asDict())
        wfd = defer.waitForDeferred(d)
        yield wfd
        tup = wfd.getResult()
        # check that (bsid, brids) were properly stored
        if not isinstance(tup, (int, dict)):
            log.err("(ignored) while trying to force build")

