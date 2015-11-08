class Change extends Factory
    constructor: (Base, dataService) ->
        return class ChangeInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)
