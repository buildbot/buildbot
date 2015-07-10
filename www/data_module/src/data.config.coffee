class HttpConfig extends Config
    constructor: ($httpProvider) ->
        # configure $http service to combine processing
        # of multiple http responses received at around
        # the same time via $rootScope.$applyAsync
        $httpProvider.useApplyAsync(true)
        ### @ngInject ###
        $httpProvider.interceptors.push ($log, API) ->
            return request: (config) ->
                # log API request only
                if config.url.indexOf(API) is 0
                    $log.debug("#{config.method} #{config.url}")
                return config
