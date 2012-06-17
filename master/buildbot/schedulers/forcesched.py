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

DefaultField = object()  # sentinel object to signal default behavior

class BaseParameter(object):
    name = ""
    parentName = None
    label = ""
    type = []
    default = ""
    required = False
    multiple = False
    regex = None
    debug=True

    @property
    def fullName(self):
        # join with '_' if both are set
        if self.parentName and self.name:
            return self.parentName+'_'+self.name
        # otherwise just use the one that is set
        # (this allows empty name for "anonymous nests")
        return self.name or self.parentName

    def setParent(self, parent):
        self.parentName = parent.fullName if parent else None

    def __init__(self, name, label=None, regex=None, **kw):
        self.name = name
        self.label = name if label is None else label
        if regex:
            self.regex = re.compile(regex)
        # all other properties are generically passed via **kw
        self.__dict__.update(kw)

    def getFromKwargs(self, kwargs):
        args = kwargs.get(self.fullName, [])
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
        if arg is None:
            raise ValidationError("need %s: no default provided by config"
                    % (self.fullName,))
        return arg

    def updateFromKwargs(self, properties, kwargs, **unused):
        properties[self.name] = self.getFromKwargs(kwargs)

    def parse_from_args(self, l):
        if self.multiple:
            return map(self.parse_from_arg, l)
        else:
            return self.parse_from_arg(l[0])

    def parse_from_arg(self, s):
        return s


class FixedParameter(BaseParameter):
    type = ["fixed"]
    hide = True
    default = ""

    def parse_from_args(self, l):
        return self.default


class StringParameter(BaseParameter):
    type = ["text"]
    size = 10

    def parse_from_arg(self, s):
        return s


class TextParameter(StringParameter):
    type = ["textarea"]
    cols = 80
    rows = 20

    def value_to_text(self, value):
        return str(value)


class IntParameter(StringParameter):
    type = ["int"]

    parse_from_arg = int # will throw an exception if parse fail


class BooleanParameter(BaseParameter):
    type = ["bool"]

    def getFromKwargs(self, kwargs):
        return kwargs.get(self.fullName, None) == [True]


class UserNameParameter(StringParameter):
    type = ["text"]
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
                        "form 'User <email@email.com>'" % (self.name,))
        return s


class ChoiceStringParameter(BaseParameter):
    type = ["list"]
    choices = []
    strict = True

    def parse_from_arg(self, s):
        if self.strict and not s in self.choices:
            raise ValidationError("'%s' does not belongs to list of available choices '%s'"%(s, self.choices))
        return s



class InheritBuildParameter(ChoiceStringParameter):
    type = ChoiceStringParameter.type + ["inherit"]
    name = "inherit"
    compatible_builds = None

    def getFromKwargs(self, kwargs):
        raise ValidationError("InheritBuildParameter can only be used by properties")

    def updateFromKwargs(self, master, properties, changes, kwargs, **unused):
        arg = kwargs.get(self.fullName, [""])[0]
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


class NestedParameter(BaseParameter):
    type = ['nested']
    fields = None
    
    def __init__(self, name, fields, label=None, **kwargs):
        BaseParameter.__init__(self, fields=fields, name=name, **kwargs)
        
        # fix up the child nodes with the parent (use None for now):
        self.setParent(None)
    
    def setParent(self, parent):
        BaseParameter.setParent(self, parent)
        for field in self.fields:
            field.setParent(self)        
    
    def collectChildProperties(self, kwargs, properties, **kw):
        # intended to be called from child classes. This fixes up the child parameters
        # into a dictionary named for the parent
        
        childProperties = {}
        for field in self.fields:
            field.updateFromKwargs(kwargs=kwargs,
                                   properties=childProperties,
                                   **kw)
                
        kwargs[self.fullName] = childProperties

    def updateFromKwargs(self, kwargs, properties, **kw):
        self.collectChildProperties(kwargs=kwargs, properties=properties, **kw)
        
        # default behavior is to set a property
        properties[self.name] = kwargs[self.fullName]
        
class AnyPropertyParameter(NestedParameter):
    type = NestedParameter.type + ["any"]

    def __init__(self, name, **kw):
        fields = [
            StringParameter(name='name', label="Name:"),
            StringParameter(name='value', label="Value:"),
        ]
        NestedParameter.__init__(self, name, fields=fields, **kw)

    def getFromKwargs(self, kwargs):
        raise ValidationError("AnyPropertyParameter can only be used by properties")

    def updateFromKwargs(self, master, properties, kwargs, **kw):
        self.collectChildProperties(master=master,
                                    properties=properties,
                                    kwargs=kwargs,
                                    **kw)
        
        pname = kwargs[self.fullName].get("name", "")
        pvalue = kwargs[self.fullName].get("value", "")
        if not pname:
            return

        validation = master.config.validation
        pname_validate = validation['property_name']
        pval_validate = validation['property_value']

        if not pname_validate.match(pname) \
                or not pval_validate.match(pvalue):
            raise ValidationError("bad property name='%s', value='%s'" % (pname, pvalue))
        properties[pname] = pvalue


class CodebaseParameter(NestedParameter):
    type = NestedParameter.type + ["codebase"]
    codebase = ''
    
    def __init__(self,
                 codebase,
                 name=None,
                 
                 branch=DefaultField,
                 revision=DefaultField,
                 repository=DefaultField,
                 project=DefaultField,
                 
                 **kwargs):

        name = name or codebase

        if branch is DefaultField:
            branch = StringParameter(name='branch', label="Branch:")
        if revision is DefaultField:
            revision = StringParameter(name='revision', label="Revision:")
        if repository is DefaultField:
            repository = StringParameter(name='repository', label="Repository:")
        if project is DefaultField:
            project = StringParameter(name='project', label="Project:")

        fields = filter(None, [branch, revision, repository, project])

        NestedParameter.__init__(self,
                                 name=name, codebase=codebase,
                                 fields=fields, **kwargs)

    def updateFromKwargs(self, sourcestamps, kwargs, **kw):
        self.collectChildProperties(sourcestamps=sourcestamps,
                                    kwargs=kwargs,
                                    **kw)
 
        # convert the "property" to a sourcestamp
        ss = kwargs.get(self.fullName, None)
        if ss:
            sourcestamps[self.codebase] = ss


class ForceScheduler(base.BaseScheduler):
    
    compare_attrs = ( 'name', 'builderNames',
                     'reason', 'username',
                     'forcedProperties' )

    def __init__(self, name, builderNames,
            username=UserNameParameter(),
            reason=StringParameter(name="reason", default="force build", length=20),

            codebases=None,
            
            branch=None,
            revision=None,
            repository=None,
            project=None,
            
            properties=[
                AnyPropertyParameter("property1"),
                AnyPropertyParameter("property2"),
                AnyPropertyParameter("property3"),
                AnyPropertyParameter("property4"),
            ]):

        self.reason = reason
        self.username = username
        
        self.forcedProperties = []
        
        if any((branch, revision, repository, project)):
            if codebases:
                raise ValidationError("Must either specify 'codebases' or the 'branch/revision/repository/project' parameters")
            
            codesbases = [
                CodebaseParameter(codebase='',
                                  branch=branch or DefaultField,
                                  revision=revision or DefaultField,
                                  repository=repository or DefaultField,
                                  project=project or DefaultField,
                                  )
            ]

        # Use the default single codebase form if none are provided
        if codebases is None:
            codebases =[CodebaseParameter(codebase='')]
        
        codebase_dict = {}
        for codebase in codebases:
            if isinstance(codebase, basestring):
                codebase = CodebaseParameter(codebase=codebase)
            elif not isinstance(codebase, CodebaseParameter):
                raise ValidationError("'codebases' must be a list of strings or CodebaseParameter objects")

            self.forcedProperties.append(codebase)
            codebase_dict[codebase.codebase] = dict(branch='',repository='',revision='')

        base.BaseScheduler.__init__(self,
                                    name=name,
                                    builderNames=builderNames,
                                    properties={},
                                    codebases=codebase_dict)

        self.forcedProperties.extend(properties)
            
        # this is used to simplify the template
        self.all_fields = [ username, reason ]
        self.all_fields.extend(self.forcedProperties)

    def startService(self):
        pass

    def stopService(self):
        pass

    @defer.inlineCallbacks
    def gatherPropertiesAndChanges(self, **kwargs):
        properties = {}
        changeids = []
        sourcestamps = {}

        for param in self.forcedProperties:
            yield defer.maybeDeferred(param.updateFromKwargs,
                                      master=self.master,
                                      properties=properties,
                                      changes=changeids,
                                      sourcestamps=sourcestamps,
                                      kwargs=kwargs)

        changeids = map(lambda a: type(a)==int and a or a.number, changeids)

        real_properties = Properties()
        for pname, pvalue in properties.items():
            real_properties.setProperty(pname, pvalue, "Force Build Form")

        defer.returnValue((real_properties, changeids, sourcestamps))

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
            return

        # Currently the validation code expects all kwargs to be lists
        # I don't want to refactor that now so much sure we comply...
        kwargs = dict((k, [v]) if not isinstance(v, list) else (k,v) for k,v in kwargs.items())

        # probably need to clean that out later as the IProperty is already a
        # validation mechanism

        reason = self.reason.getFromKwargs(kwargs)
        if owner is None:
            owner = self.username.getFromKwargs(kwargs)

        properties, changeids, sourcestamps = yield self.gatherPropertiesAndChanges(**kwargs)

        properties.setProperty("reason", reason, "Force Build Form")
        properties.setProperty("owner", owner, "Force Build Form")

        r = ("A build was forced by '%s': %s" % (owner, reason))

        # everything is validated, we can create our source stamp, and buildrequest
        res = yield self.addBuildsetForSourceStampSetDetails(
            reason = r,
            sourcestamps = sourcestamps,
            properties = properties,
            )

        defer.returnValue(res)
