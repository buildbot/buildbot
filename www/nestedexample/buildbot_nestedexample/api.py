
import json

from klein import Klein
from twisted.internet import defer


class Api:
    app = Klein()
    pizzaIngredients = {'margherita': ['tomato', 'ham', 'cheese'],
                        'regina': ['tomato', 'ham', 'cheese', 'mushrooms']}

    def __init__(self, ep):
        self.ep = ep

    @app.route("/getIngredients", methods=['GET'])
    def getIngredients(self, request):
        pizzaArgument = request.args.get('pizza')
        if pizzaArgument is None:
            return defer.succeed(json.dumps("invalid request"))
        pizza = pizzaArgument[0].lower()
        res = self.pizzaIngredients.get(pizza,
                                        ["only {} are supported "
                                         "for now".format(self.pizzaIngredients.keys())])
        return defer.succeed(json.dumps(res))
