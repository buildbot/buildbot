define(function () {

    "use strict";
    var screenSize;

	screenSize = {
        isSmallScreen: function() {
			var smallScreen = $(".container-inner").width() <= 570;
			return smallScreen;
		},
		isMediumScreen: function() {
			var mediumScreen = $(".container-inner").width() <= 768;
			return mediumScreen;
		} 
	}
	 return screenSize;
});