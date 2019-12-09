/*
 * decaffeinate suggestions:
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Route {
    constructor($urlRouterProvider, glMenuServiceProvider, config) {
        let apptitle;
        $urlRouterProvider.otherwise(config.default_page || '/');
        // the app title needs to be < 18 chars else the UI looks bad
        // we try to find best option
        if (config.title != null) {
            apptitle = `Buildbot: ${config.title}`;
            if (apptitle.length > 18) {
                apptitle = config.title;
            }
            if (apptitle.length > 18) {
                apptitle = "Buildbot";
            }
        } else {
            apptitle = "Buildbot";
        }
        glMenuServiceProvider.setAppTitle(apptitle);
    }
}
        // all states config are in the modules


angular.module('app')
.config(['$urlRouterProvider', 'glMenuServiceProvider', 'config', Route])
.config(['$locationProvider', function($locationProvider) {
    $locationProvider.hashPrefix('');
}]);
