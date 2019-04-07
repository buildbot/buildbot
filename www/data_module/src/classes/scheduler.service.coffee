class Scheduler
    constructor: (Base, dataService) ->
        return class SchedulerInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)


angular.module('app')
.factory('Scheduler', ['Base', 'dataService', Scheduler])