class Step extends Factory
    constructor: (Base, dataService) ->
        return class BuildInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'logs'           # /logs
                ]

                super(object, endpoint, endpoints)
