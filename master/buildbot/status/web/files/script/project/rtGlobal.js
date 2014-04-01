define(['jquery', 'helpers'], function ($, helpers) {
         "use strict";
        var buildQueueTotal = $('#buildQueueTotal');
        var buildSlavesTotal = $('#buildSlavesTotal');
        var outerBar = $('#verticalProgressBar');        

        var rtGlobal = {
        init: function () {            
            helpers.verticalProgressBar(outerBar.children());        
            outerBar.attr('title',""+16+ " builds are running, "+43+" agents are idle ");
        }
    };

    return rtGlobal;
});