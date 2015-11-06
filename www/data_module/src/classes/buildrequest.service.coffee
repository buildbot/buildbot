class Buildrequest extends Factory
    constructor: (Base, dataService) ->
        return class BuildrequestInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'builds'            # /builds
                ]

                super(object, endpoint, endpoints)
