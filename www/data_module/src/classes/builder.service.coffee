class Builder
    constructor: (Base, dataService) ->
        return class BuilderInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'builds'            # /builds/:buildid
                    'buildrequests'     # /buildrequests/:buildrequestid
                    'forceschedulers'   # /forceschedulers
                    'workers'           # /workers/:workerid
                                        # /workers/:name
                    'masters'           # /masters/:masterid
                ]

                super(object, endpoint, endpoints)


angular.module('app')
.factory('Builder', ['Base', 'dataService', Builder])