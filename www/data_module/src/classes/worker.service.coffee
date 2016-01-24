class Worker extends Factory
    constructor: (Base, dataService) ->
        return class WorkerInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)
