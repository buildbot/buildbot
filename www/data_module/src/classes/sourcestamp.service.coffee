class Sourcestamp
    constructor: (Base, dataService) ->
        return class SourcestampInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'changes'           # /changes
                ]

                super(object, endpoint, endpoints)


angular.module('app')
.factory('Sourcestamp', ['Base', 'dataService', Sourcestamp])