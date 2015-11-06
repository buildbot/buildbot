class Api extends Constant
    constructor: -> return 'api/v2/'

class Endpoints extends Constant
    constructor: ->
        # Rootlinks
        return [
            'builders'
            'builds'
            'buildrequests'
            'buildslaves'
            'buildsets'
            'changes'
            'changesources'
            'masters'
            'sourcestamps'
            'schedulers'
            'forceschedulers'
        ]
