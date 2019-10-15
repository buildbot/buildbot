/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// I intercept the http errors and put them in the notification service
// in order to enable it, please add following code in you config:

//class AddInterceptor extends Config
//    constructor: ($httpProvider) ->
//        $httpProvider.responseInterceptors.push('glHttpInterceptor')


class glHttpInterceptor {
    constructor(glNotificationService, $q, $timeout) {
        return function(promise) {
            const errorHandler =  function(res) {
                let msg;
                try {
                    msg = `${res.status}:${res.data.error} ` +
                    `when:${res.config.method} ${res.config.url}`;
                } catch (e) {
                    msg = res.toString();
                }
                $timeout((() => glNotificationService.network(msg)), 100);
                $q.resolve(null);
            };

            return promise.then(angular.identity, errorHandler);
        };
    }
}


angular.module('guanlecoja.ui')
.factory('glHttpInterceptor', ['glNotificationService', '$q', '$timeout', glHttpInterceptor]);
