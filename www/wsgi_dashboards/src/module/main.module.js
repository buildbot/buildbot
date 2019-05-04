// Register new module
class WsgiDashboards {
    constructor() { return [
        'ui.router', 'buildbot_config', 'guanlecoja.ui'
    ]; }
}

angular.module('wsgi_dashboards', new WsgiDashboards());

const context = require.context('./', true, /^(?!.*(?:module|spec|webpack.js$)).*\.js$/);
context.keys().forEach(context);
