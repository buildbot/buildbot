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

import traceback
import re
from twisted.internet import defer
try:
    import email.utils as email_utils
    email_utils = email_utils
except ImportError:
    # Python-2.4 capitalization
    import email.Utils as email_utils

from buildbot.process.properties import Properties
from buildbot.schedulers import base

class BaseParameter(object):
    name = ""
    label = ""
    type = ""
    default = ""
    required = False
    multiple = False
    regex = None
    debug=True

    def __init__(self, name, label=None, regex=None, **kw):
        self.label = self.name = name
        if label:
            self.label = label
        if regex:
            self.regex = re.compile(regex)
        # all other properties are generically passed via **kw
        self.__dict__.update(kw)

    def update_from_post(self, master, properties, changes, req):
        args = req.args.get(self.name, [])
        if len(args) == 0:
            if self.required:
                raise ValueError("'%s' needs to be specified" % (self.label))
            if self.multiple:
                args = self.default
            else:
                args = [self.default]
        if self.regex:
            for arg in args:
                if not self.regex.match(arg):
                    raise ValueError("%s:'%s' does not match pattern '%s'"
                            % (self.label, arg, self.regex.pattern))
        try:
            arg = self.parse_from_args(args)
        except Exception, e:
            # an exception will just display an alert in the web UI
            # also log the exception
            if self.debug:
                traceback.print_exc()
            raise e
        if arg == None:
            raise ValueError("need %s: no default provided by config"
                    % (self.name,))
        properties[self.name] = arg

    def parse_from_args(self, l):
        if self.multiple:
            return map(self.parse_from_arg, l)
        else:
            return self.parse_from_arg(l[0])

    def parse_from_arg(self, s):
        return s


class FixedParameter(BaseParameter):
    type = "fixed"
    hide = True
    default = ""

    def parse_from_args(self, l):
        return self.default


class StringParameter(BaseParameter):
    type = "text"
    size = 10

    def parse_from_arg(self, s):
        return s


class TextParameter(StringParameter):
    type = "textarea"
    cols = 80
    rows = 20

    def value_to_text(self, value):
        return str(value)


class IntParameter(StringParameter):
    type = "int"

    parse_from_arg = int # will throw an exception if parse fail


class BooleanParameter(BaseParameter):
    type = "bool"

    def update_from_post(self, master, properties, changes, req):
        # damn html's ungeneric checkbox implementation...
        checkbox = req.args.get("checkbox", [""])
        properties[self.name] = self.name in checkbox


class UserNameParameter(StringParameter):
    type = "text"
    default = ""
    size = 30
    need_email = True

    def __init__(self, name="username", label="Your name:", **kw):
        BaseParameter.__init__(self, name, label, **kw)

    def parse_from_arg(self, s):
        if self.need_email:
            e = email_utils.parseaddr(s)
            if e[0]=='' or e[1] == '':
                raise ValueError("%s: please fill in email address in the "
                        " form User <email@email.com>" % (self.label,))
        return s


class ChoiceStringParameter(BaseParameter):
    type = "list"
    choices = []
    strict = True

    def parse_from_arg(self, s):
        if self.strict and not s in self.choices:
            raise ValueError("'%s' does not belongs to list of available choices '%s'"%(s, self.choices))
        return s


class InheritBuildParameter(ChoiceStringParameter):
    name = "inherit"
    compatible_builds = None

    def update_from_post(self, master, properties, changes, req):
        arg = req.args.get(self.name, [""])[0]
        splitted_arg = arg.split(" ")[0].split("/")
        if len(splitted_arg) != 2:
            raise ValueError("bad build: %s"%(arg))
        builder, num = splitted_arg
        builder_status = master.status.getBuilder(builder)
        if not builder_status:
            raise ValueError("unknown builder: %s in %s"%(builder, arg))
        b = builder_status.getBuild(int(num))
        if not b:
            raise ValueError("unknown build: %d in %s"%(num, arg))
        props = {self.name:(arg.split(" ")[0])}
        for name, value, source in b.getProperties().asList():
            if source == "Force Build Form":
                if name == "owner":
                    name = "orig_owner"
                props[name] = value
        properties.update(props)
        changes.extend(b.changes)


class AnyPropertyParameter(BaseParameter):
    type = "anyproperty"

    def update_from_post(self, master, properties, changes, req):
        validation = master.config.validation
        pname = req.args.get("%sname" % self.name, [""])[0]
        pvalue = req.args.get("%svalue" % self.name, [""])[0]
        if not pname:
            return
        pname_validate = validation['property_name']
        pval_validate = validation['property_value']
        if not pname_validate.match(pname) \
                or not pval_validate.match(pvalue):
            raise ValueError("bad property name='%s', value='%s'" % (pname, pvalue))
        properties[pname] = pvalue


class ForceScheduler(base.BaseScheduler):
    
    compare_attrs = ( 'name', 'builderNames', 'branch', 'reason',
            'revision', 'repository', 'project', 'forcedProperties' )

    def __init__(self, name, builderNames,
            branch=StringParameter(name="branch",default=""), 
            reason=StringParameter(name="reason", default="force build"),
            revision=StringParameter(name="revision",default=""),
            repository=StringParameter(name="repository",default=""),
            project=StringParameter(name="project",default=""),
            username=UserNameParameter(),
            properties=[
                AnyPropertyParameter("property1"),
                AnyPropertyParameter("property2"),
                AnyPropertyParameter("property3"),
                AnyPropertyParameter("property4"),
            ]):

        base.BaseScheduler.__init__(self, name=name,
                builderNames=builderNames,properties={})
        self.branch = branch
        self.reason = reason
        self.repository = repository
        self.revision = revision
        self.project = project
        self.username = username
        self.forcedProperties = properties
        # this is used to simplify the template
        self.all_fields = [ branch, username, reason, repository,
                            revision, project ]
        self.all_fields.extend(properties)

    def startService(self):
        pass

    def stopService(self):
        pass

    def forceWithWebRequest(self, owner, builder_name, req):
        """Called by the web UI.
        Authentication is already done, thus owner is passed as argument
        We check the parameters, and launch the build, if everything is correct
        """
        if not builder_name in self.builderNames:
            # in the case of buildAll, this method will be called several times
            # for all the builders
            # we just do nothing on a builder that is not in our builderNames
            return defer.succeed(None)
        master = self.master
        properties = {}
        changeids = []
        # probably need to clean that out later as the IProperty is already a
        # validation mechanism

        validation = master.config.validation
        if self.branch.regex == None:
            self.branch.regex = validation['branch']
        if self.revision.regex == None:
            self.revision.regex = validation['revision']

        for param in self.all_fields:
            if owner and param==self.username:
                continue # dont enforce username if auth
            param.update_from_post(master, properties, changeids, req)

        changeids = map(lambda a: type(a)==int and a or a.number, changeids)
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

        r = ("The web-page 'force build' button was pressed by '%s': %s\n"
             % (owner, reason)) 

        d = master.db.sourcestampsets.addSourceStampSet()
        def add_master_with_setid(sourcestampsetid):
            master.db.sourcestamps.addSourceStamp(
                                    sourcestampsetid = sourcestampsetid,
                                    branch=branch,
                                    revision=revision, project=project, 
                                    repository=repository,changeids=changeids)
            return sourcestampsetid
            
        d.addCallback(add_master_with_setid)
        def got_setid(sourcestampsetid):
            return self.addBuildsetForSourceStamp(builderNames=[builder_name],
                                    setid=sourcestampsetid, reason=r,
                                    properties=real_properties)
        d.addCallback(got_setid)
        return d
