
// setup ace to fetch its module from the plugin baseURL
class AceConfig {
    constructor($location) {
        const baseurl = $location.absUrl().split("#")[0];
        window.ace.config.set("basePath", `${baseurl}codeparameter`);
    }
}

// defines custom field directives which only have templates
class Codefield {
    constructor() {
        return {
            replace: false,
            restrict: 'E',
            scope: false,
            template: require('./codefield.tpl.jade')
        };
    }
}

angular.module('codeparameter')
.run(['$location', AceConfig])
.directive('codefield', [Codefield]);
