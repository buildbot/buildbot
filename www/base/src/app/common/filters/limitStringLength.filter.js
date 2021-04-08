var limitStringLength = function ($filter) {
    function limitStringLength(input, limit) {
        var newContent = $filter('limitTo')(input, limit);
        if(input.length > limit) { newContent += ' ...'; }
        return newContent;
    }
    return limitStringLength;
}

angular.module('common')
    .filter('limitStringLengthTo', ['$filter', limitStringLength]);
