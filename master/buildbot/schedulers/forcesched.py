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

import email.utils as email_utils
import re
import traceback

from twisted.internet import defer

from buildbot import config
from buildbot.process.properties import Properties
from buildbot.schedulers import base


class ValidationError(ValueError):
    pass

DefaultField = object()  # sentinel object to signal default behavior


class BaseParameter(object):

    """
    BaseParameter provides a base implementation for property customization
    """
    name = ""
    parentName = None
    label = ""
    type = []
    default = ""
    required = False
    multiple = False
    regex = None
    debug = True
    hide = False

    @property
    def fullName(self):
        """A full name, intended to uniquely identify a parameter"""
        # join with '_' if both are set
        if self.parentName and self.name:
            return self.parentName + '_' + self.name
        # otherwise just use the one that is set
        # (this allows empty name for "anonymous nests")
        return self.name or self.parentName

    def setParent(self, parent):
        self.parentName = parent.fullName if parent else None

    def __init__(self, name, label=None, regex=None, **kw):
        """
        @param name: the name of the field, used during posting values
                     back to the scheduler. This is not necessarily a UI value,
                     and there may be restrictions on the characters allowed for
                     this value. For example, HTML would require this field to
                     avoid spaces and other punctuation ('-', '.', and '_' allowed)
        @type name: unicode

        @param label: (optional) the name of the field, used for UI display.
        @type label: unicode or None (to use 'name')

        @param regex: (optional) regex to validate the value with. Not used by
                      all subclasses
        @type regex: unicode or regex
        """

        self.name = name
        self.label = name if label is None else label
        if regex:
            self.regex = re.compile(regex)
        # all other properties are generically passed via **kw
        self.__dict__.update(kw)

    def getFromKwargs(self, kwargs):
        """Simple customization point for child classes that do not need the other
           parameters supplied to updateFromKwargs. Return the value for the property
           named 'self.name'.

           The default implementation converts from a list of items, validates using
           the optional regex field and calls 'parse_from_args' for the final conversion.
        """
        args = kwargs.get(self.fullName, [])

        # delete white space for args
        for arg in args:
            if not arg.strip():
                args.remove(arg)

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
        """Primary entry point to turn 'kwargs' into 'properties'"""
        properties[self.name] = self.getFromKwargs(kwargs)

    def parse_from_args(self, l):
        """Secondary customization point, called from getFromKwargs to turn
           a validated value into a single property value"""
        if self.multiple:
            return map(self.parse_from_arg, l)
        else:
            return self.parse_from_arg(l[0])

    def parse_from_arg(self, s):
        return s


class FixedParameter(BaseParameter):

    """A fixed parameter that cannot be modified by the user."""
    type = ["fixed"]
    hide = True
    default = ""

    def parse_from_args(self, l):
        return self.default


class StringParameter(BaseParameter):

    """A simple string parameter"""
    type = ["text"]
    size = 10

    def parse_from_arg(self, s):
        return s


class TextParameter(StringParameter):

    """A generic string parameter that may span multiple lines"""
    type = ["textarea"]
    cols = 80
    rows = 20

    def value_to_text(self, value):
        return str(value)


class IntParameter(StringParameter):

    """An integer parameter"""
    type = ["int"]

    parse_from_arg = int  # will throw an exception if parse fail


class BooleanParameter(BaseParameter):

    """A boolean parameter"""
    type = ["bool"]

    def getFromKwargs(self, kwargs):
        return kwargs.get(self.fullName, None) == [True]


class UserNameParameter(StringParameter):

    """A username parameter to supply the 'owner' of a build"""
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
            if e[0] == '' or e[1] == '':
                raise ValidationError("%s: please fill in email address in the "
                                      "form 'User <email@email.com>'" % (self.name,))
        return s


class ChoiceStringParameter(BaseParameter):

    """A list of strings, allowing the selection of one of the predefined values.
       The 'strict' parameter controls whether values outside the predefined list
       of choices are allowed"""
    type = ["list"]
    choices = []
    strict = True

    def parse_from_arg(self, s):
        if self.strict and s not in self.choices:
            raise ValidationError("'%s' does not belongs to list of available choices '%s'" % (s, self.choices))
        return s

    def getChoices(self, master, scheduler, buildername):
        return self.choices


class InheritBuildParameter(ChoiceStringParameter):

    """A parameter that takes its values from another build"""
    type = ChoiceStringParameter.type + ["inherit"]
    name = "inherit"
    compatible_builds = None

    def getChoices(self, master, scheduler, buildername):
        return self.compatible_builds(master.status, buildername)

    def getFromKwargs(self, kwargs):
        raise ValidationError("InheritBuildParameter can only be used by properties")

    def updateFromKwargs(self, master, properties, changes, kwargs, **unused):
        arg = kwargs.get(self.fullName, [""])[0]
        splitted_arg = arg.split(" ")[0].split("/")
        if len(splitted_arg) != 2:
            raise ValidationError("bad build: %s" % (arg))
        builder, num = splitted_arg
        builder_status = master.status.getBuilder(builder)
        if not builder_status:
            raise ValidationError("unknown builder: %s in %s" % (builder, arg))
        b = builder_status.getBuild(int(num))
        if not b:
            raise ValidationError("unknown build: %d in %s" % (num, arg))
        props = {self.name: (arg.split(" ")[0])}
        for name, value, source in b.getProperties().asList():
            if source == "Force Build Form":
                if name == "owner":
                    name = "orig_owner"
                props[name] = value
        properties.update(props)
        changes.extend(b.changes)


class BuildslaveChoiceParameter(ChoiceStringParameter):

    """A parameter that lets the buildslave name be explicitly chosen.

    This parameter works in conjunction with 'buildbot.process.builder.enforceChosenSlave',
    which should be added as the 'canStartBuild' parameter to the Builder.

    The "anySentinel" parameter represents the sentinel value to specify that
    there is no buildslave preference.
    """
    anySentinel = '-any-'
    label = 'Build slave'
    required = False
    strict = False

    def __init__(self, name='slavename', **kwargs):
        ChoiceStringParameter.__init__(self, name, **kwargs)

    def updateFromKwargs(self, kwargs, **unused):
        slavename = self.getFromKwargs(kwargs)
        if slavename == self.anySentinel:
            # no preference, so dont set a parameter at all
            return
        ChoiceStringParameter.updateFromKwargs(self, kwargs=kwargs, **unused)

    def getChoices(self, master, scheduler, buildername):
        if buildername is None:
            # this is the "Force All Builds" page
            slavenames = master.status.getSlaveNames()
        else:
            builderStatus = master.status.getBuilder(buildername)
            slavenames = [slave.getName() for slave in builderStatus.getSlaves()]
        slavenames.sort()
        slavenames.insert(0, self.anySentinel)
        return slavenames


class NestedParameter(BaseParameter):

    """A 'parent' parameter for a set of related parameters. This provides a
       logical grouping for the child parameters.

       Typically, the 'fullName' of the child parameters mix in the parent's
       'fullName'. This allows for a field to appear multiple times in a form
       (for example, two codebases each have a 'branch' field).

       If the 'name' of the parent is the empty string, then the parent's name
       does not mix in with the child 'fullName'. This is useful when a field
       will not appear multiple time in a scheduler but the logical grouping is
       helpful.

       The result of a NestedParameter is typically a dictionary, with the key/value
       being the name/value of the children.
    """
    type = ['nested']
    fields = None

    def __init__(self, name, fields, **kwargs):
        BaseParameter.__init__(self, fields=fields, name=name, **kwargs)

        # fix up the child nodes with the parent (use None for now):
        self.setParent(None)

    def setParent(self, parent):
        BaseParameter.setParent(self, parent)
        for field in self.fields:
            field.setParent(self)

    def collectChildProperties(self, kwargs, properties, **kw):
        """Collapse the child values into a dictionary. This is intended to be
           called by child classes to fix up the fullName->name conversions."""

        childProperties = {}
        for field in self.fields:
            field.updateFromKwargs(kwargs=kwargs,
                                   properties=childProperties,
                                   **kw)

        kwargs[self.fullName] = childProperties

    def updateFromKwargs(self, kwargs, properties, **kw):
        """By default, the child values will be collapsed into a dictionary. If
        the parent is anonymous, this dictionary is the top-level properties."""
        self.collectChildProperties(kwargs=kwargs, properties=properties, **kw)

        # default behavior is to set a property
        #  -- use setdefault+update in order to collapse 'anonymous' nested
        #     parameters correctly
        if self.name:
            d = properties.setdefault(self.name, {})
        else:
            # if there's no name, collapse this nest all the way
            d = properties
        d.update(kwargs[self.fullName])


class AnyPropertyParameter(NestedParameter):

    """A generic property parameter, where both the name and value of the property
       must be given."""
    type = NestedParameter.type + ["any"]

    def __init__(self, name, **kw):
        fields = [
            StringParameter(name='name', label="Name:"),
            StringParameter(name='value', label="Value:"),
        ]
        NestedParameter.__init__(self, name, label='', fields=fields, **kw)

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

    """A parameter whose result is a codebase specification instead of a property"""
    type = NestedParameter.type + ["codebase"]
    codebase = ''

    def __init__(self,
                 codebase,
                 name=None,
                 label=None,

                 branch=DefaultField,
                 revision=DefaultField,
                 repository=DefaultField,
                 project=DefaultField,

                 **kwargs):
        """
        A set of properties that will be used to generate a codebase dictionary.

        The branch/revision/repository/project should each be a parameter that
        will map to the corresponding value in the sourcestamp. Use None to disable
        the field.

        @param codebase: name of the codebase; used as key for the sourcestamp set
        @type codebase: unicode

        @param name: optional override for the name-currying for the subfields
        @type codebase: unicode

        @param label: optional override for the label for this set of parameters
        @type codebase: unicode
        """

        name = name or codebase
        if label is None and codebase:
            label = "Codebase: " + codebase

        if branch is DefaultField:
            branch = StringParameter(name='branch', label="Branch:")
        if revision is DefaultField:
            revision = StringParameter(name='revision', label="Revision:")
        if repository is DefaultField:
            repository = StringParameter(name='repository', label="Repository:")
        if project is DefaultField:
            project = StringParameter(name='project', label="Project:")

        fields = filter(None, [branch, revision, repository, project])

        NestedParameter.__init__(self, name=name, label=label,
                                 codebase=codebase,
                                 fields=fields, **kwargs)

    def createSourcestamp(self, properties, kwargs):
        # default, just return the things we put together
        return kwargs.get(self.fullName, {})

    def updateFromKwargs(self, sourcestamps, kwargs, properties, **kw):
        self.collectChildProperties(sourcestamps=sourcestamps,
                                    properties=properties,
                                    kwargs=kwargs,
                                    **kw)

        # convert the "property" to a sourcestamp
        ss = self.createSourcestamp(properties, kwargs)
        if ss is not None:
            sourcestamps[self.codebase] = ss


class ForceScheduler(base.BaseScheduler):

    """
    ForceScheduler implements the backend for a UI to allow customization of
    builds. For example, a web form be populated to trigger a build.
    """
    compare_attrs = ('name', 'builderNames',
                     'reason', 'username',
                     'forcedProperties')

    def __init__(self, name, builderNames,
                 username=UserNameParameter(),
                 reason=StringParameter(name="reason", default="force build", size=20),
                 reasonString="A build was forced by '%(owner)s': %(reason)s",
                 buttonName="Force Build",
                 codebases=None,

                 properties=[
                     NestedParameter(name='', fields=[
                         AnyPropertyParameter("property1"),
                         AnyPropertyParameter("property2"),
                         AnyPropertyParameter("property3"),
                         AnyPropertyParameter("property4"),
                     ])
                 ],

                 # deprecated; use 'codebase' instead
                 branch=None,
                 revision=None,
                 repository=None,
                 project=None
                 ):
        """
        Initialize a ForceScheduler.

        The UI will provide a set of fields to the user; these fields are
        driven by a corresponding child class of BaseParameter.

        Use NestedParameter to provide logical groupings for parameters.

        The branch/revision/repository/project fields are deprecated and
        provided only for backwards compatibility. Using a Codebase(name='')
        will give the equivalent behavior.

        @param name: name of this scheduler (used as a key for state)
        @type name: unicode

        @param builderNames: list of builders this scheduler may start
        @type builderNames: list of unicode

        @param username: the "owner" for a build (may not be shown depending
                         on the Auth configuration for the master)
        @type username: BaseParameter

        @param reason: the "reason" for a build
        @type reason: BaseParameter

        @param codebases: the codebases for a build
        @type codebases: list of string's or CodebaseParameter's;
                         None will generate a default, but [] will
                         remove all codebases

        @param properties: extra properties to configure the build
        @type properties: list of BaseParameter's
        """

        if not self.checkIfType(name, str):
            config.error("ForceScheduler name must be a unicode string: %r" %
                         name)

        if not name:
            config.error("ForceScheduler name must not be empty: %r " %
                         name)

        if not self.checkIfListOfType(builderNames, str):
            config.error("ForceScheduler '%s': builderNames must be a list of strings: %r" %
                         (name, builderNames))

        if self.checkIfType(reason, BaseParameter):
            self.reason = reason
        else:
            config.error("ForceScheduler '%s': reason must be a StringParameter: %r" %
                         (name, reason))

        if not self.checkIfListOfType(properties, BaseParameter):
            config.error("ForceScheduler '%s': properties must be a list of BaseParameters: %r" %
                         (name, properties))

        if self.checkIfType(username, BaseParameter):
            self.username = username
        else:
            config.error("ForceScheduler '%s': username must be a StringParameter: %r" %
                         (name, username))

        self.forcedProperties = []

        if any((branch, revision, repository, project)):
            if codebases:
                config.error("ForceScheduler '%s': Must either specify 'codebases' or the 'branch/revision/repository/project' parameters: %r " % (name, codebases))

            codebases = [
                CodebaseParameter(codebase='',
                                  branch=branch or DefaultField,
                                  revision=revision or DefaultField,
                                  repository=repository or DefaultField,
                                  project=project or DefaultField,
                                  )
            ]

        # Use the default single codebase form if none are provided
        if codebases is None:
            codebases = [CodebaseParameter(codebase='')]
        elif not codebases:
            config.error("ForceScheduler '%s': 'codebases' cannot be empty; use CodebaseParameter(codebase='', hide=True) if needed: %r " % (name, codebases))

        codebase_dict = {}
        for codebase in codebases:
            if isinstance(codebase, basestring):
                codebase = CodebaseParameter(codebase=codebase)
            elif not isinstance(codebase, CodebaseParameter):
                config.error("ForceScheduler '%s': 'codebases' must be a list of strings or CodebaseParameter objects: %r" % (name, codebases))

            self.forcedProperties.append(codebase)
            codebase_dict[codebase.codebase] = dict(branch='', repository='', revision='')

        base.BaseScheduler.__init__(self,
                                    name=name,
                                    builderNames=builderNames,
                                    properties={},
                                    codebases=codebase_dict)

        if properties:
            self.forcedProperties.extend(properties)

        # this is used to simplify the template
        self.all_fields = [NestedParameter(name='', fields=[username, reason])]
        self.all_fields.extend(self.forcedProperties)

        self.reasonString = reasonString
        self.buttonName = buttonName

    def checkIfType(self, obj, chkType):
        return isinstance(obj, chkType)

    def checkIfListOfType(self, obj, chkType):
        isListOfType = True

        if self.checkIfType(obj, list):
            for item in obj:
                if not self.checkIfType(item, chkType):
                    isListOfType = False
                    break
        else:
            isListOfType = False

        return isListOfType

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

        changeids = map(lambda a: isinstance(a, int) and a or a.number, changeids)

        real_properties = Properties()
        for pname, pvalue in properties.items():
            real_properties.setProperty(pname, pvalue, "Force Build Form")

        defer.returnValue((real_properties, changeids, sourcestamps))

    @defer.inlineCallbacks
    def force(self, owner, builderNames=None, **kwargs):
        """
        We check the parameters, and launch the build, if everything is correct
        """
        if builderNames is None:
            builderNames = self.builderNames
        else:
            builderNames = set(builderNames).intersection(self.builderNames)

        if not builderNames:
            defer.returnValue(None)
            return

        # Currently the validation code expects all kwargs to be lists
        # I don't want to refactor that now so much sure we comply...
        kwargs = dict((k, [v]) if not isinstance(v, list) else (k, v) for k, v in kwargs.items())

        # probably need to clean that out later as the IProperty is already a
        # validation mechanism

        reason = self.reason.getFromKwargs(kwargs)
        if owner is None:
            owner = self.username.getFromKwargs(kwargs)

        properties, changeids, sourcestamps = yield self.gatherPropertiesAndChanges(**kwargs)

        properties.setProperty("reason", reason, "Force Build Form")
        properties.setProperty("owner", owner, "Force Build Form")

        r = self.reasonString % {'owner': owner, 'reason': reason}

        # everything is validated, we can create our source stamp, and buildrequest
        res = yield self.addBuildsetForSourceStampSetDetails(
            reason=r,
            sourcestamps=sourcestamps,
            properties=properties,
            builderNames=builderNames,
        )

        defer.returnValue(res)
