# Register new module
class WsgiDashboards
    constructor: -> return [
        'ui.router', 'buildbot_config', 'guanlecoja.ui'
    ]


angular.module('app', new WsgiDashboards())