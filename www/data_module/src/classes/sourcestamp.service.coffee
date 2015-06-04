class Sourcestamp extends Factory
    constructor: (Base, dataService) ->
        return class SourcestampInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'changes'           # /changes
                ]

                super(object, endpoint, endpoints)
