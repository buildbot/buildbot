class Changesource
    constructor: (dataService, Base) ->
        return class ChangesourceInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)


angular.module('app')
.factory('Changesource', ['dataService', 'Base', Changesource])