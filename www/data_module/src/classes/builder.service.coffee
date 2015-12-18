class Builder extends Factory
    constructor: (Base, dataService) ->
        return class BuilderInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'builds'            # /builds/:buildid
                    'buildrequests'     # /buildrequests/:buildrequestid
                    'forceschedulers'   # /forceschedulers
                    'buildslaves'       # /buildslaves/:buildslaveid
                                        # /buildslaves/:name
                    'masters'           # /masters/:masterid
                ]

                super(object, endpoint, endpoints)
