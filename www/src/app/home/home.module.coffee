name = 'buildbot.home'
dependencies = [
    'buildbot.common'
    'ui.router'
]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)