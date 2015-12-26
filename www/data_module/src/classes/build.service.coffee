class Build extends Factory
    constructor: (Base, dataService) ->
        return class BuildInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'changes'           # /changes
                    'properties'        # /properties
                    'steps'             # /steps/:name
                                        # /steps/:stepid
                ]

                super(object, endpoint, endpoints)
