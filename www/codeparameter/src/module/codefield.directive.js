// Register new module
class Codeparameter {
    constructor() { return [
        'ui.ace',
        'common'
    ]; }
}

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
            templateUrl: "codeparameter/views/codefield.html"
        };
    }
}


angular.module('codeparameter', new Codeparameter())
.run(['$location', AceConfig])
.directive('codefield', [Codefield]);
