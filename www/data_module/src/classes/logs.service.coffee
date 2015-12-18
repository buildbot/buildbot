class Log extends Factory
    constructor: (Base, dataService) ->
        return class BuildInstance extends Base
            constructor: (object, endpoint) ->
                endpoints = [
                    'chunks'           # /chunks
                    'contents'
                ]
                super(object, endpoint, endpoints)
