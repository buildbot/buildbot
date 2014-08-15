class AddInterceptor extends Config
    constructor: ($httpProvider) ->
        $httpProvider.responseInterceptors.push('interceptor')

class Interceptor extends Factory
    constructor: (alert, $q, $timeout) ->
        return (promise) ->
            promise.then (res) ->
                res
            , (res, bla) ->
                try
                    msg = "Error: #{res.status}:#{res.data.error} " +
                        "when:#{res.config.method} #{res.config.url}"
                    # as mq events is not yet competly implemented serverside,
                    # we dont alert on those errors
                    # they are just in the debug log
                    if res.config.url.indexOf("sse/") >= 0
                        return
                catch e
                    msg = res.toString()
                $timeout ->
                    alert.error(msg)
                , 100
                $q.reject res