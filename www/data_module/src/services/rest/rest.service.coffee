class Rest extends Service
    constructor: ($http, $q, API) ->
        return new class RestService
            execute: (config) ->
                $q (resolve, reject) ->
                    $http(config)
                    .success (response) ->
                        try
                            data = angular.fromJson(response)
                            resolve(data)
                        catch e
                            reject(e)
                    .error (reason) -> reject(reason)

            get: (url, params = {}) ->
                canceller = $q.defer()
                config =
                    method: 'GET'
                    url: @parse(API, url)
                    params: params
                    headers:
                        'Accept': 'application/json'
                    timeout: canceller.promise

                promise = @execute(config)
                promise.cancel = canceller.resolve
                return promise

            post: (url, data = {}) ->
                canceller = $q.defer()
                config =
                    method: 'POST'
                    url: @parse(API, url)
                    data: data
                    headers:
                        'Content-Type': 'application/json'
                    timeout: canceller.promise

                promise = @execute(config)
                promise.cancel = canceller.resolve
                return promise

            parse: (args...) ->
                args.join('/').replace(/\/\//, '/')
