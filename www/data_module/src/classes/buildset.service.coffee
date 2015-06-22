class Buildset extends Factory
    constructor: (Base, dataService) ->
        return class BuildsetInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'properties'        # /properties
                ]

                super(object, endpoint, endpoints)
