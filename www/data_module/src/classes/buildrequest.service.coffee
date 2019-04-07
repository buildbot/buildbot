class Buildrequest
    constructor: (Base, dataService) ->
        return class BuildrequestInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'builds'            # /builds
                ]

                super(object, endpoint, endpoints)


angular.module('app')
.factory('Buildrequest', ['Base', 'dataService', Buildrequest])