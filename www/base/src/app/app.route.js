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

        // Note that we warn about too long title in master/buildbot/config.py.
        // Adjust that code if the maximum length changes.
        let max_title_len = 18;

        if (config.title != null) {
            apptitle = `Buildbot: ${config.title}`;
            if (apptitle.length > max_title_len) {
                apptitle = config.title;
            }
            if (apptitle.length > max_title_len) {
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
