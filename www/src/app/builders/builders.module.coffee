name = 'buildbot.builders'
dependencies = [
    'ui.router'
    'ui.bootstrap'
    'RecursionHelper'
    'buildbot.common'
]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)