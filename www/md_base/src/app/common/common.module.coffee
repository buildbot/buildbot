name = 'common'
dependencies = [
    'ui.router'
]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)
