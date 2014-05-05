define(function () {

    "use strict";
    var screenSize;

	screenSize = {
        isSmallScreen: function() {
			var smallScreen = $(window).width() <= 570;
			return smallScreen;
		},
		isMediumScreen: function() {
			var mediumScreen = $(window).width() <= 768;
			return mediumScreen;
		},
		isLargeScreen: function() {
			var largeScreen = $(window).width() >= 1025;			
			return largeScreen;
		} 
	}
	 return screenSize;
});