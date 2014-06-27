name = 'buildbot.about'
dependencies = [
    'ui.router'
    'buildbot.common'
    'bowerconfigs'
]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)