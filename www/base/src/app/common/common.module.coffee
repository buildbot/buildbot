name = 'common'
dependencies = [
    'ui.router'
    'RecursionHelper'
]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)
