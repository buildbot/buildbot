const dependencies = [
    'ui.router',
    'RecursionHelper'
];

// Register new module
angular.module('common', dependencies);
angular.module('app').requires.push('common');
