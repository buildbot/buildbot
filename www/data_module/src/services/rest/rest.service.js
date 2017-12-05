/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Rest {
    constructor($http, $q, API) {
        let RestService;
        return new (RestService = class RestService {
            execute(config) {
                return $q((resolve, reject) =>
                    $http(config)
                    .success(function(response) {
                        try {
                            const data = angular.fromJson(response);
                            return resolve(data);
                        } catch (e) {
                            return reject(e);
                        }}).error(reason => reject(reason))
                );
            }

            get(url, params) {
                if (params == null) { params = {}; }
                const canceller = $q.defer();
                const config = {
                    method: 'GET',
                    url: this.parse(API, url),
                    params,
                    headers: {
                        'Accept': 'application/json'
                    },
                    timeout: canceller.promise
                };

                const promise = this.execute(config);
                promise.cancel = canceller.resolve;
                return promise;
            }

            post(url, data) {
                if (data == null) { data = {}; }
                const canceller = $q.defer();
                const config = {
                    method: 'POST',
                    url: this.parse(API, url),
                    data,
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    timeout: canceller.promise
                };

                const promise = this.execute(config);
                promise.cancel = canceller.resolve;
                return promise;
            }

            parse(...args) {
                return args.join('/').replace(/\/\//, '/');
            }
        });
    }
}


angular.module('app')
.service('restService', ['$http', '$q', 'API', Rest]);