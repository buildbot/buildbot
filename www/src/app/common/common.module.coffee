name = 'buildbot.common'
dependencies = [
    'ui.router'
    'restangular'
    'RecursionHelper'
]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)