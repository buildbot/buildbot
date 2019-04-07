class Worker
    constructor: (Base, dataService) ->
        return class WorkerInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)


angular.module('app')
.factory('Worker', ['Base', 'dataService', Worker])