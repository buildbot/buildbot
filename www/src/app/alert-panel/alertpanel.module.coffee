name = 'buildbot.alertpanel'
dependencies = [

]

# Register new module
angular.module name, dependencies
angular.module('app').requires.push(name)