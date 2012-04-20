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
import email.utils as email_utils

from buildbot.process.properties import Properties
from buildbot.schedulers import base

class ValidationError(ValueError):
    pass

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

    def getFromKwargs(self, kwargs):
        args = kwargs.get(self.name, [])
        if len(args) == 0:
            if self.required:
                raise ValidationError("'%s' needs to be specified" % (self.label))
            if self.multiple:
                args = self.default
            else:
                args = [self.default]
        if self.regex:
            for arg in args:
                if not self.regex.match(arg):
                    raise ValidationError("%s:'%s' does not match pattern '%s'"
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
            raise ValidationError("need %s: no default provided by config"
                    % (self.name,))
        return arg

    def updateFromKwargs(self, master, properties, changes, kwargs):
        properties[self.name] = self.getFromKwargs(kwargs)

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

    def getFromKwargs(self, kwargs):
        return self.name in kwargs and kwargs[self.name] == True


class UserNameParameter(StringParameter):
    type = "text"
    default = ""
    size = 30
    need_email = True

    def __init__(self, name="username", label="Your name:", **kw):
        BaseParameter.__init__(self, name, label, **kw)

    def parse_from_arg(self, s):
        if not s and not self.required:
            return s
        if self.need_email:
            e = email_utils.parseaddr(s)
            if e[0]=='' or e[1] == '':
                raise ValidationError("%s: please fill in email address in the "
                        " form User <email@email.com>" % (self.label,))
        return s


class ChoiceStringParameter(BaseParameter):
    type = "list"
    choices = []
    strict = True

    def parse_from_arg(self, s):
        if self.strict and not s in self.choices:
            raise ValidationError("'%s' does not belongs to list of available choices '%s'"%(s, self.choices))
        return s


class InheritBuildParameter(ChoiceStringParameter):
    name = "inherit"
    compatible_builds = None

    def getFromKwargs(self, kwargs):
        raise ValidationError("InheritBuildParameter can only be used by properties")

    def updateFromKwargs(self, master, properties, changes, kwargs):
        arg = kwargs.get(self.name, [""])[0]
        splitted_arg = arg.split(" ")[0].split("/")
        if len(splitted_arg) != 2:
            raise ValidationError("bad build: %s"%(arg))
        builder, num = splitted_arg
        builder_status = master.status.getBuilder(builder)
        if not builder_status:
            raise ValidationError("unknown builder: %s in %s"%(builder, arg))
        b = builder_status.getBuild(int(num))
        if not b:
            raise ValidationError("unknown build: %d in %s"%(num, arg))
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

    def getFromKwargs(self, kwargs):
        raise ValidationError("AnyPropertyParameter can only be used by properties")

    def updateFromKwargs(self, master, properties, changes, kwargs):
        validation = master.config.validation
        pname = kwargs.get("%sname" % self.name, [""])[0]
        pvalue = kwargs.get("%svalue" % self.name, [""])[0]
        if not pname:
            return
        pname_validate = validation['property_name']
        pval_validate = validation['property_value']
        if not pname_validate.match(pname) \
                or not pval_validate.match(pvalue):
            raise ValidationError("bad property name='%s', value='%s'" % (pname, pvalue))
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

    @defer.inlineCallbacks
    def gatherPropertiesAndChanges(self, **kwargs):
        properties = {}
        changeids = []

        for param in self.forcedProperties:
            yield defer.maybeDeferred(param.updateFromKwargs, self.master, properties, changeids, kwargs)

        changeids = map(lambda a: type(a)==int and a or a.number, changeids)

        real_properties = Properties()
        for pname, pvalue in properties.items():
            real_properties.setProperty(pname, pvalue, "Force Build Form")

        defer.returnValue((real_properties, changeids))

    def forceWithWebRequest(self, owner, builder_name, req):
        """Called by the web UI.
        Authentication is already done, thus owner is passed as argument
        """
        args = {}
        # damn html's ungeneric checkbox implementation...
        for cb in req.args.get("checkbox", []):
            args[cb] = True
        args.update(req.args)

        return self.force(owner, builder_name, **args)

    @defer.inlineCallbacks
    def force(self, owner, builder_name, **kwargs):
        """
        We check the parameters, and launch the build, if everything is correct
        """
        if not builder_name in self.builderNames:
            # in the case of buildAll, this method will be called several times
            # for all the builders
            # we just do nothing on a builder that is not in our builderNames
            defer.returnValue(None)

        # probably need to clean that out later as the IProperty is already a
        # validation mechanism

        validation = self.master.config.validation
        if self.branch.regex == None:
            self.branch.regex = validation['branch']
        if self.revision.regex == None:
            self.revision.regex = validation['revision']

        reason = self.reason.getFromKwargs(kwargs)
        branch = self.branch.getFromKwargs(kwargs)
        revision = self.revision.getFromKwargs(kwargs)
        repository = self.repository.getFromKwargs(kwargs)
        project = self.project.getFromKwargs(kwargs)
        if owner is None:
            owner = self.owner.getFromKwargs(kwargs)

        properties, changeids = yield self.gatherPropertiesAndChanges(**kwargs)

        properties.setProperty("reason", reason, "Force Build Form")
        properties.setProperty("owner", owner, "Force Build Form")

        r = ("The web-page 'force build' button was pressed by '%s': %s"
             % (owner, reason)) 

        # everything is validated, we can create our source stamp, and buildrequest
        res = yield self.schedule(builder_name, branch, revision, repository, project, changeids, properties, r)
        defer.returnValue(res)

    @defer.inlineCallbacks
    def schedule(self, builder, branch, revision, repository, project, changeids, properties, reason):
        sourcestampsetid = yield self.master.db.sourcestampsets.addSourceStampSet()

        yield self.master.db.sourcestamps.addSourceStamp(
                                sourcestampsetid = sourcestampsetid,
                                branch=branch,
                                revision=revision, project=project,
                                repository=repository,changeids=changeids)

        retval = yield self.addBuildsetForSourceStamp(builderNames=[builder],
                                    setid=sourcestampsetid, reason=reason,
                                    properties=properties)

        defer.returnValue(retval)

