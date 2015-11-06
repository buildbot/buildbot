class Master extends Factory
    constructor: (Base, dataService) ->
        return class MasterInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'builders'          # /builders/:builderid
                    'buildslaves'       # /buildslaves/:buildslaveid
                                        # /buildslaves/:name
                    'changesources'     # /changesources/:changesourceid
                    'schedulers'        # /schedulers/:schedulerid
                ]

                super(object, endpoint, endpoints)
