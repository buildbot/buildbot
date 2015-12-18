class Buildslave extends Factory
    constructor: (Base, dataService) ->
        return class BuildslaveInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)
