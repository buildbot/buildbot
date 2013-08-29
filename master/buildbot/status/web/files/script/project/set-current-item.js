define(['jquery'], function ($) {
	
    "use strict";
    var setCurrentItem;
    
    setCurrentItem = {
        init: function () {

			
				var path = window.location.pathname.split("\/");

				 $('.top-menu a').each(function(index) {
				 	var thishref = this.href.split("\/");
				    if(thishref[thishref.length-1].trim().toLowerCase() == path[1].trim().toLowerCase())
				        $(this).parent().addClass("selected");
				});
			
		}
	};

    return setCurrentItem;
});