class Scheduler extends Factory
    constructor: (Base, dataService) ->
        return class SchedulerInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)
