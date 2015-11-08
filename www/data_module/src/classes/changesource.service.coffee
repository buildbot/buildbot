class Changesource extends Factory
    constructor: (dataService, Base) ->
        return class ChangesourceInstance extends Base
            constructor: (object, endpoint) ->
                super(object, endpoint)
