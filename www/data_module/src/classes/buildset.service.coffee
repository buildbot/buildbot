class Buildset
    constructor: (Base, dataService) ->
        return class BuildsetInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'properties'        # /properties
                ]

                super(object, endpoint, endpoints)


angular.module('app')
.factory('Buildset', ['Base', 'dataService', Buildset])