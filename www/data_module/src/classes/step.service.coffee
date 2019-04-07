class Step
    constructor: (Base, dataService) ->
        return class BuildInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'logs'           # /logs
                ]

                super(object, endpoint, endpoints)


angular.module('app')
.factory('Step', ['Base', 'dataService', Step])