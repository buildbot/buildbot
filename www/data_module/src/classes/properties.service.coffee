# damn grammar. I claim that properties singular is propertie
class Propertie extends Factory
    constructor: (Base, dataService) ->
        return class BuildInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint, [])
