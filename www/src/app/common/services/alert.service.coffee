angular.module('app').factory 'alert', ['$rootScope', ($rootScope) ->

    alert = (msg, type) ->
        type ?= 'danger'
        $rootScope.$broadcast 'alert', type:type, msg: msg

    alert.error = (msg) ->
        alert msg, 'danger'

    alert.warning = (msg) ->
        alert msg, 'info'

    alert.success = (msg) ->
        alert msg, 'success'
    window.alert = alert
    return alert
]
angular.module('app').config ['$httpProvider', ($httpProvider) ->
    $httpProvider.responseInterceptors.push ["alert", "$q", "$timeout", (alert, $q, $timeout) ->
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
    ]

]
