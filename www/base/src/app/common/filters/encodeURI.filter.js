var encodeURI = function ($filter) {
    function encodeURI(input) {
        return window.encodeURIComponent((input == null) ? "" : input);
    }
    return encodeURI;
}

angular.module('common')
    .filter('encodeURI', ['$filter', encodeURI]);
