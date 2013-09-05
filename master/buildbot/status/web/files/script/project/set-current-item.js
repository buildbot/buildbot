define(['jquery'], function ($) {
	
    "use strict";
    var setCurrentItem;
    
    setCurrentItem = {
        init: function () {
			
				var path = window.location.pathname.split("\/");
				
				 $('.top-menu a').each(function(index) {
				 	var thishref = this.href.split("\/");
				 	
				    if(this.id == path[1].trim().toLowerCase() || (this.id == 'home' && path[1].trim().toLowerCase().length === 0))
				        $(this).parent().addClass("selected");
				});
			
		}
	};

    return setCurrentItem;
});