# damn grammar. I claim that properties singular is propertie
class Propertie
    constructor: (Base, dataService) ->
        return class BuildInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint, [])


angular.module('app')
.factory('Propertie', ['Base', 'dataService', Propertie])