const dependencies = [
    'ui.router',
    'RecursionHelper',
    'buildbot_config'
];

// Register new module
angular.module('common', dependencies);
angular.module('app').requires.push('common');
