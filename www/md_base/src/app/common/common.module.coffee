name = 'common'
dependencies = [
    'ui.router'
    'restangular'
]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)
