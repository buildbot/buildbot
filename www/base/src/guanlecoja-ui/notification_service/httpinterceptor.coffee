# I intercept the http errors and put them in the notification service
# in order to enable it, please add following code in you config:

#class AddInterceptor extends Config
#    constructor: ($httpProvider) ->
#        $httpProvider.responseInterceptors.push('glHttpInterceptor')


class glHttpInterceptor
    constructor: (glNotificationService, $q, $timeout) ->
        return (promise) ->
            errorHandler =  (res) ->
                try
                    msg = "#{res.status}:#{res.data.error} " +
                    "when:#{res.config.method} #{res.config.url}"
                catch e
                    msg = res.toString()
                $timeout((-> glNotificationService.network(msg)), 100)
                $q.reject res

            promise.then(angular.identity, errorHandler)


angular.module('guanlecoja.ui')
.factory('glHttpInterceptor', ['glNotificationService', '$q', '$timeout', glHttpInterceptor])
