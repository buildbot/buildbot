class HttpConfig extends Config
    constructor: ($httpProvider) ->
        # configure $http service to combine processing
        # of multiple http responses received at around
        # the same time via $rootScope.$applyAsync
        $httpProvider.useApplyAsync(true)


class Dataconfig extends Constant
    constructor: ->
        return {
            enableIndexedDB: false
            enableTabex: false
        }
