class Forcescheduler extends Factory
    constructor: (Base, dataService) ->
        return class ForceschedulerInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)
