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

import re
import traceback

from twisted.internet import defer
from twisted.python.reflect import accumulateClassList

from buildbot import config
from buildbot.process.properties import Properties
from buildbot.reporters.mail import VALID_EMAIL_ADDR
from buildbot.schedulers import base
from buildbot.util import identifiers


class ValidationError(ValueError):
    pass


class CollectedValidationError(ValueError):

    def __init__(self, errors):
        self.errors = errors
        super().__init__("\n".join([k + ":" + v for k, v in errors.items()]))


class ValidationErrorCollector:

    def __init__(self):
        self.errors = {}

    @defer.inlineCallbacks
    def collectValidationErrors(self, name, fn, *args, **kwargs):
        res = None
        try:
            res = yield fn(*args, **kwargs)
        except CollectedValidationError as e:
            for error_name, e in e.errors.items():
                self.errors[error_name] = e
        except ValueError as e:
            self.errors[name] = str(e)
        return res

    def maybeRaiseCollectedErrors(self):
        errors = self.errors
        if errors:
            raise CollectedValidationError(errors)


DefaultField = object()  # sentinel object to signal default behavior


class BaseParameter:

    """
    BaseParameter provides a base implementation for property customization
    """
    spec_attributes = ["name", "fullName", "label", "tablabel", "type", "default", "required",
                       "multiple", "regex", "hide", "maxsize", "autopopulate"]
    name = ""
    parentName = None
    label = ""
    tablabel = ""
    type = ""
    default = ""
    required = False
    multiple = False
    regex = None
    debug = True
    hide = False
    maxsize = None
    autopopulate = None

    @property
    def fullName(self):
        """A full name, intended to uniquely identify a parameter"""
        # join with '_' if both are set (cannot put '.', because it is used as
        # **kwargs)
        if self.parentName and self.name:
            return self.parentName + '_' + self.name
        # otherwise just use the one that is set
        # (this allows empty name for "anonymous nests")
        return self.name or self.parentName

    def setParent(self, parent):
        self.parentName = parent.fullName if parent else None

    def __init__(self, name, label=None, tablabel=None, regex=None, **kw):
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

        if name in ["owner", "builderNames", "builderid"]:
            config.error(f"{name} cannot be used as a parameter name, because it is reserved")
        self.name = name
        self.label = name if label is None else label
        self.tablabel = self.label if tablabel is None else tablabel
        if regex:
            self.regex = re.compile(regex)
        if 'value' in kw:
            config.error(f"Use default='{kw['value']}' instead of value=... to give a "
                         "default Parameter value")
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
            if isinstance(arg, str) and not arg.strip():
                args.remove(arg)

        if not args:
            if self.required:
                raise ValidationError(f"'{self.label}' needs to be specified")
            if self.multiple:
                args = self.default
            else:
                args = [self.default]

        if self.regex:
            for arg in args:
                if not self.regex.match(arg):
                    raise ValidationError(f"{self.label}:'{arg}' does not match pattern "
                                          f"'{self.regex.pattern}'")
        if self.maxsize is not None:
            for arg in args:
                if len(arg) > self.maxsize:
                    raise ValidationError(f"{self.label}: is too large {len(arg)} > {self.maxsize}")

        try:
            arg = self.parse_from_args(args)
        except Exception as e:
            # an exception will just display an alert in the web UI
            # also log the exception
            if self.debug:
                traceback.print_exc()
            raise e
        if arg is None:
            raise ValidationError(f"need {self.fullName}: no default provided by config")
        return arg

    def updateFromKwargs(self, properties, kwargs, collector, **unused):
        """Primary entry point to turn 'kwargs' into 'properties'"""
        properties[self.name] = self.getFromKwargs(kwargs)

    def parse_from_args(self, l):
        """Secondary customization point, called from getFromKwargs to turn
           a validated value into a single property value"""
        if self.multiple:
            return [self.parse_from_arg(arg) for arg in l]
        return self.parse_from_arg(l[0])

    def parse_from_arg(self, s):
        return s

    def getSpec(self):
        spec_attributes = []
        accumulateClassList(self.__class__, 'spec_attributes', spec_attributes)
        ret = {}
        for i in spec_attributes:
            ret[i] = getattr(self, i)
        return ret


class FixedParameter(BaseParameter):

    """A fixed parameter that cannot be modified by the user."""
    type = "fixed"
    hide = True
    default = ""

    def parse_from_args(self, l):
        return self.default


class StringParameter(BaseParameter):

    """A simple string parameter"""
    spec_attributes = ["size"]
    type = "text"
    size = 10

    def parse_from_arg(self, s):
        return s


class TextParameter(StringParameter):

    """A generic string parameter that may span multiple lines"""
    spec_attributes = ["cols", "rows"]
    type = "textarea"
    cols = 80
    rows = 20

    def value_to_text(self, value):
        return str(value)


class IntParameter(StringParameter):

    """An integer parameter"""
    type = "int"
    default = 0
    parse_from_arg = int  # will throw an exception if parse fail


class BooleanParameter(BaseParameter):

    """A boolean parameter"""
    type = "bool"

    def getFromKwargs(self, kwargs):
        return kwargs.get(self.fullName, [self.default]) == [True]


class UserNameParameter(StringParameter):

    """A username parameter to supply the 'owner' of a build"""
    spec_attributes = ["need_email"]
    type = "username"
    default = ""
    size = 30
    need_email = True

    def __init__(self, name="username", label="Your name:", **kw):
        super().__init__(name, label, **kw)

    def parse_from_arg(self, s):
        if not s and not self.required:
            return s
        if self.need_email:
            res = VALID_EMAIL_ADDR.search(s)
            if res is None:
                raise ValidationError(f"{self.name}: please fill in email address in the "
                                      "form 'User <email@email.com>'")
        return s


class ChoiceStringParameter(BaseParameter):

    """A list of strings, allowing the selection of one of the predefined values.
       The 'strict' parameter controls whether values outside the predefined list
       of choices are allowed"""
    spec_attributes = ["choices", "strict"]
    type = "list"
    choices = []
    strict = True

    def parse_from_arg(self, s):
        if self.strict and s not in self.choices:
            raise ValidationError(f"'{s}' does not belong to list of available choices "
                                  f"'{self.choices}'")
        return s

    def getChoices(self, master, scheduler, buildername):
        return self.choices


class InheritBuildParameter(ChoiceStringParameter):

    """A parameter that takes its values from another build"""
    type = ChoiceStringParameter.type
    name = "inherit"
    compatible_builds = None

    def getChoices(self, master, scheduler, buildername):
        return self.compatible_builds(master, buildername)

    def getFromKwargs(self, kwargs):
        raise ValidationError(
            "InheritBuildParameter can only be used by properties")

    def updateFromKwargs(self, master, properties, changes, kwargs, **unused):
        arg = kwargs.get(self.fullName, [""])[0]
        split_arg = arg.split(" ")[0].split("/")
        if len(split_arg) != 2:
            raise ValidationError(f"bad build: {arg}")
        builder_name, build_num = split_arg

        builder_dict = master.data.get(('builders', builder_name))
        if builder_dict is None:
            raise ValidationError(f"unknown builder: {builder_name} in {arg}")

        build_dict = master.data.get(('builders', builder_name, 'builds', build_num),
                                     fields=['properties'])
        if build_dict is None:
            raise ValidationError(f"unknown build: {builder_name} in {arg}")

        props = {self.name: (arg.split(" ")[0])}
        for name, (value, source) in build_dict['properties']:
            if source == "Force Build Form":
                if name == "owner":
                    name = "orig_owner"
                props[name] = value
        properties.update(props)
        # FIXME: this does not do what we expect, but updateFromKwargs is not used either.
        # This needs revisiting when the build parameters are fixed:
        # changes.extend(b.changes)


class WorkerChoiceParameter(ChoiceStringParameter):

    """A parameter that lets the worker name be explicitly chosen.

    This parameter works in conjunction with 'buildbot.process.builder.enforceChosenWorker',
    which should be added as the 'canStartBuild' parameter to the Builder.

    The "anySentinel" parameter represents the sentinel value to specify that
    there is no worker preference.
    """
    anySentinel = '-any-'
    label = 'Worker'
    required = False
    strict = False

    def __init__(self, name='workername', **kwargs):
        super().__init__(name, **kwargs)

    def updateFromKwargs(self, kwargs, **unused):
        workername = self.getFromKwargs(kwargs)
        if workername == self.anySentinel:
            # no preference, so don't set a parameter at all
            return
        super().updateFromKwargs(kwargs=kwargs, **unused)

    @defer.inlineCallbacks
    def getChoices(self, master, scheduler, buildername):
        if buildername is None:
            # this is the "Force All Builds" page
            workers = yield self.master.data.get(('workers',))
        else:
            builder = yield self.master.data.get(('builders', buildername))
            workers = yield self.master.data.get(('builders', builder['builderid'], 'workers'))

        workernames = [worker['name'] for worker in workers]
        workernames.sort()
        workernames.insert(0, self.anySentinel)
        return workernames


class FileParameter(BaseParameter):
    """A parameter which allows to download a whole file and store it as a property or patch
    """
    type = 'file'
    maxsize = 1024 * 1024 * 10  # 10M


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
    spec_attributes = [
        "layout", "columns"]  # field is recursive, and thus managed in custom getSpec
    type = 'nested'
    layout = 'vertical'
    fields = None
    columns = None

    def __init__(self, name, fields, **kwargs):
        super().__init__(fields=fields, name=name, **kwargs)
        # reasonable defaults for the number of columns
        if self.columns is None:
            num_visible_fields = len(
                [field for field in fields if not field.hide])
            if num_visible_fields >= 4:
                self.columns = 2
            else:
                self.columns = 1
        if self.columns > 4:
            config.error(
                "UI only support up to 4 columns in nested parameters")

        # fix up the child nodes with the parent (use None for now):
        self.setParent(None)

    def setParent(self, parent):
        super().setParent(parent)
        for field in self.fields:  # pylint: disable=not-an-iterable
            field.setParent(self)

    @defer.inlineCallbacks
    def collectChildProperties(self, kwargs, properties, collector, **kw):
        """Collapse the child values into a dictionary. This is intended to be
           called by child classes to fix up the fullName->name conversions."""

        childProperties = {}
        for field in self.fields:  # pylint: disable=not-an-iterable
            yield collector.collectValidationErrors(field.fullName,
                                                    field.updateFromKwargs,
                                                    kwargs=kwargs,
                                                    properties=childProperties,
                                                    collector=collector,
                                                    **kw)
        kwargs[self.fullName] = childProperties

    @defer.inlineCallbacks
    def updateFromKwargs(self, kwargs, properties, collector, **kw):
        """By default, the child values will be collapsed into a dictionary. If
        the parent is anonymous, this dictionary is the top-level properties."""
        yield self.collectChildProperties(kwargs=kwargs, properties=properties,
                                          collector=collector, **kw)
        # default behavior is to set a property
        #  -- use setdefault+update in order to collapse 'anonymous' nested
        #     parameters correctly
        if self.name:
            d = properties.setdefault(self.name, {})
        else:
            # if there's no name, collapse this nest all the way
            d = properties
        d.update(kwargs[self.fullName])

    def getSpec(self):
        ret = super().getSpec()
        # pylint: disable=not-an-iterable
        ret['fields'] = [field.getSpec() for field in self.fields]
        return ret


ParameterGroup = NestedParameter


class AnyPropertyParameter(NestedParameter):

    """A generic property parameter, where both the name and value of the property
       must be given."""
    type = NestedParameter.type

    def __init__(self, name, **kw):
        fields = [
            StringParameter(name='name', label="Name:"),
            StringParameter(name='value', label="Value:"),
        ]
        super().__init__(name, label='', fields=fields, **kw)

    def getFromKwargs(self, kwargs):
        raise ValidationError(
            "AnyPropertyParameter can only be used by properties")

    @defer.inlineCallbacks
    def updateFromKwargs(self, master, properties, kwargs, collector, **kw):
        yield self.collectChildProperties(master=master,
                                          properties=properties,
                                          kwargs=kwargs,
                                          collector=collector,
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
            raise ValidationError(f"bad property name='{pname}', value='{pvalue}'")
        properties[pname] = pvalue


class CodebaseParameter(NestedParameter):

    """A parameter whose result is a codebase specification instead of a property"""
    type = NestedParameter.type
    codebase = ''

    def __init__(self,
                 codebase,
                 name=None,
                 label=None,

                 branch=DefaultField,
                 revision=DefaultField,
                 repository=DefaultField,
                 project=DefaultField,
                 patch=None,

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

        fields_dict = dict(branch=branch, revision=revision,
                           repository=repository, project=project)
        for k, v in fields_dict.items():
            if v is DefaultField:
                v = StringParameter(name=k, label=k.capitalize() + ":")
            elif isinstance(v, str):
                v = FixedParameter(name=k, default=v)
            fields_dict[k] = v

        fields = [val for k, val in sorted(fields_dict.items(), key=lambda x: x[0]) if val]
        if patch is not None:
            if patch.name != "patch":
                config.error(
                    "patch parameter of a codebase must be named 'patch'")
            fields.append(patch)
            if self.columns is None and 'columns' not in kwargs:
                self.columns = 1

        super().__init__(name=name, label=label,
                         codebase=codebase,
                         fields=fields, **kwargs)

    def createSourcestamp(self, properties, kwargs):
        # default, just return the things we put together
        return kwargs.get(self.fullName, {})

    @defer.inlineCallbacks
    def updateFromKwargs(self, sourcestamps, kwargs, properties, collector, **kw):
        yield self.collectChildProperties(sourcestamps=sourcestamps,
                                          properties=properties,
                                          kwargs=kwargs,
                                          collector=collector,
                                          **kw)

        # convert the "property" to a sourcestamp
        ss = self.createSourcestamp(properties, kwargs)
        if ss is not None:
            patch = ss.pop('patch', None)
            if patch is not None:
                for k, v in patch.items():
                    ss['patch_' + k] = v

            sourcestamps[self.codebase] = ss


def oneCodebase(**kw):
    return [CodebaseParameter('', **kw)]


class PatchParameter(NestedParameter):
    """A patch parameter contains pre-configure UI for all the needed components for a
       sourcestamp patch
    """
    columns = 1

    def __init__(self, **kwargs):
        name = kwargs.pop('name', 'patch')
        default_fields = [
            FileParameter('body'),
            IntParameter('level', default=1),
            StringParameter('author', default=""),
            StringParameter('comment', default=""),
            StringParameter('subdir', default=".")
        ]
        fields = [
            kwargs.pop(field.name, field)
            for field in default_fields
        ]
        super().__init__(name, fields=fields, **kwargs)


class ForceScheduler(base.BaseScheduler):

    """
    ForceScheduler implements the backend for a UI to allow customization of
    builds. For example, a web form be populated to trigger a build.
    """
    compare_attrs = base.BaseScheduler.compare_attrs + \
        ('builderNames',
         'reason', 'username',
         'forcedProperties')

    def __init__(self, name, builderNames,
                 username=UserNameParameter(),
                 reason=StringParameter(
                     name="reason", default="force build", size=20),
                 reasonString="A build was forced by '%(owner)s': %(reason)s",
                 buttonName=None,
                 codebases=None,
                 label=None,
                 properties=None):
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
                         None will generate a default, but
                         CodebaseParameter(codebase='', hide=True)
                         will remove all codebases

        @param properties: extra properties to configure the build
        @type properties: list of BaseParameter's
        """

        if not self.checkIfType(name, str):
            config.error(f"ForceScheduler name must be a unicode string: {repr(name)}")

        if not name:
            config.error(f"ForceScheduler name must not be empty: {repr(name)}")

        if not identifiers.ident_re.match(name):
            config.error(f"ForceScheduler name must be an identifier: {repr(name)}")

        if not self.checkIfListOfType(builderNames, (str,)):
            config.error(f"ForceScheduler '{name}': builderNames must be a list of strings: "
                         f"{repr(builderNames)}")

        if self.checkIfType(reason, BaseParameter):
            self.reason = reason
        else:
            config.error(f"ForceScheduler '{name}': reason must be a StringParameter: "
                         f"{repr(reason)}")

        if properties is None:
            properties = []
        if not self.checkIfListOfType(properties, BaseParameter):
            config.error(f"ForceScheduler '{name}': properties must be "
                         f"a list of BaseParameters: {repr(properties)}")

        if self.checkIfType(username, BaseParameter):
            self.username = username
        else:
            config.error(f"ForceScheduler '{name}': username must be a StringParameter: "
                         f"{repr(username)}")

        self.forcedProperties = []
        self.label = name if label is None else label

        # Use the default single codebase form if none are provided
        if codebases is None:
            codebases = [CodebaseParameter(codebase='')]
        elif not codebases:
            config.error(f"ForceScheduler '{name}': 'codebases' cannot be empty;"
                         f" use [CodebaseParameter(codebase='', hide=True)] if needed: "
                         f"{repr(codebases)} ")
        elif not isinstance(codebases, list):
            config.error(f"ForceScheduler '{name}': 'codebases' should be a list of strings "
                         f"or CodebaseParameter, not {type(codebases)}")

        codebase_dict = {}
        for codebase in codebases:
            if isinstance(codebase, str):
                codebase = CodebaseParameter(codebase=codebase)
            elif not isinstance(codebase, CodebaseParameter):
                config.error(f"ForceScheduler '{name}': 'codebases' must be a list of strings "
                             f"or CodebaseParameter objects: {repr(codebases)}")

            self.forcedProperties.append(codebase)
            codebase_dict[codebase.codebase] = dict(
                branch='', repository='', revision='')

        super().__init__(name=name,
                         builderNames=builderNames,
                         properties={},
                         codebases=codebase_dict)

        if properties:
            self.forcedProperties.extend(properties)

        # this is used to simplify the template
        self.all_fields = [NestedParameter(name='', fields=[username, reason])]
        self.all_fields.extend(self.forcedProperties)

        self.reasonString = reasonString
        self.buttonName = buttonName or name

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

    @defer.inlineCallbacks
    def gatherPropertiesAndChanges(self, collector, **kwargs):
        properties = {}
        changeids = []
        sourcestamps = {}

        for param in self.forcedProperties:
            yield collector.collectValidationErrors(param.fullName,
                                                    param.updateFromKwargs,
                                                    master=self.master,
                                                    properties=properties,
                                                    changes=changeids,
                                                    sourcestamps=sourcestamps,
                                                    collector=collector,
                                                    kwargs=kwargs)
        changeids = [type(a) == int and a or a.number for a in changeids]

        real_properties = Properties()
        for pname, pvalue in properties.items():
            real_properties.setProperty(pname, pvalue, "Force Build Form")

        return (real_properties, changeids, sourcestamps)

    @defer.inlineCallbacks
    def computeBuilderNames(self, builderNames=None, builderid=None):
        if builderNames is None:
            if builderid is not None:
                builder = yield self.master.data.get(('builders', str(builderid)))
                builderNames = [builder['name']]
            else:
                builderNames = self.builderNames
        else:
            builderNames = sorted(
                set(builderNames).intersection(self.builderNames))
        return builderNames

    @defer.inlineCallbacks
    def force(self, owner, builderNames=None, builderid=None, **kwargs):
        """
        We check the parameters, and launch the build, if everything is correct
        """
        builderNames = yield self.computeBuilderNames(builderNames, builderid)
        if not builderNames:
            raise KeyError("builderNames not specified or not supported")

        # Currently the validation code expects all kwargs to be lists
        # I don't want to refactor that now so much sure we comply...
        kwargs = dict((k, [v]) if not isinstance(v, list) else (k, v)
                      for k, v in kwargs.items())

        # probably need to clean that out later as the IProperty is already a
        # validation mechanism
        collector = ValidationErrorCollector()
        reason = yield collector.collectValidationErrors(self.reason.fullName,
                                                         self.reason.getFromKwargs, kwargs)
        if owner is None or owner == "anonymous":
            owner = yield collector.collectValidationErrors(self.username.fullName,
                                                            self.username.getFromKwargs, kwargs)

        properties, _, sourcestamps = yield self.gatherPropertiesAndChanges(
            collector, **kwargs)

        collector.maybeRaiseCollectedErrors()

        properties.setProperty("reason", reason, "Force Build Form")
        properties.setProperty("owner", owner, "Force Build Form")

        r = self.reasonString % {'owner': owner, 'reason': reason}

        # turn sourcestamps into a list
        for cb, ss in sourcestamps.items():
            ss['codebase'] = cb
        sourcestamps = list(sourcestamps.values())

        # everything is validated, we can create our source stamp, and
        # buildrequest
        res = yield self.addBuildsetForSourceStampsWithDefaults(
            reason=r,
            sourcestamps=sourcestamps,
            properties=properties,
            builderNames=builderNames,
        )

        return res
