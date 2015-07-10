class Rest extends Service
    constructor: ($http, $q, API) ->
        return new class RestService
            execute: (config) ->
                $q (resolve, reject) =>
                    $http(config)
                    .success (response) ->
                        try
                            data = angular.fromJson(response)
                            resolve(data)
                        catch e
                            reject(e)
                    .error (reason) -> reject(reason)

            get: (url, params = {}) ->
                config =
                    method: 'GET'
                    url: @parse(API, url)
                    params: params
                    headers:
                      'Accept': 'application/json'

                @execute(config)

            post: (url, data = {}) ->
                config =
                    method: 'POST'
                    url: @parse(API, url)
                    data: data
                    headers:
                        'Content-Type': 'application/json'

                @execute(config)

            parse: (args...) ->
                args.join('/').replace(/\/\//, '/')
