from twisted.internet import defer

from buildbot.schedulers.forcesched import ChoiceStringParameter
from buildbot.schedulers.forcesched import NestedParameter
from buildbot.schedulers.forcesched import StringParameter
from buildbot.schedulers.forcesched import ValidationError
from buildbot.www.plugin import Application

from .api import Api


class NestedExample(NestedParameter):

    """UI zone"""
    type = "nestedexample"
    PIZZA = "pizza"
    INGREDIENTS = "ingredients"

    def __init__(self, **kw):
        pizzaInput = StringParameter(label="type the name of your pizza",
                                     name=self.PIZZA,
                                     required=True)
        ingredientsInput = ChoiceStringParameter(name=self.INGREDIENTS,
                                                 label="ingredients necessary to make the pizza",
                                                 multiple=True,
                                                 strict=False,
                                                 default="",
                                                 choices=[])
        self.params = {self.PIZZA: pizzaInput,
                       self.INGREDIENTS: ingredientsInput}
        self.allIngredients = set(sum([ingr for ingr in Api.pizzaIngredients.values()],
                                      []))
        fields = self.params.values()
        super(NestedExample, self).__init__(self.type, label='', fields=fields, **kw)

    def createNestedPropertyName(self, propertyName):
        return "{}_{}".format(self.type, propertyName)

    @defer.inlineCallbacks
    def validateProperties(self, collector, properties):
        # we implement the check between the input and
        # the ingredients
        if properties[self.INGREDIENTS] not in self.allIngredients or\
           not properties[self.PIZZA]:
            # we trigger a specific error message in PIZZA only
            def f():
                return defer.fail(ValidationError('Invalid pizza'))
            nestedProp = self.createNestedPropertyName(self.PIZZA)
            yield collector.collectValidationErrors(nestedProp, f)

    @defer.inlineCallbacks
    def updateFromKwargs(self, kwargs, properties, collector, **kw):
        yield super(NestedExample, self).updateFromKwargs(kwargs, properties, collector, **kw)
        # the properties we have are in the form
        # {nestedexample: {input: <url>,
        #                 ingredients: <ingredients>}}
        # we just flatten the dict to have
        # - input, and
        # - ingredients
        # in properties
        for prop, val in properties.pop(self.type).items():
            properties[prop] = val
        yield self.validateProperties(collector, properties)


# create the interface for the setuptools entry point
ep = Application(__name__, "Buildbot nested parameter example")
api = Api(ep)
ep.resource.putChild("api", api.app.resource())
