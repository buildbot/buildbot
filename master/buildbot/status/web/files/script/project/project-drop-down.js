define(['screensize', 'helpers'], function (screenSize, helpers) {

    "use strict";
    var projectDropDown;

    	projectDropDown = {
	        init: function () {
			
		    
			$(window).resize(function() {
				
				if (screenSize.isSmallScreen()){	
	    			$('.project-dropdown-js').remove();
	    		} else {
	    			$('.top-menu').show();
	    			$('.submenu').remove();	
	    		}			  
			});
			
	        // mobile top menu
	    	$('.smartphone-nav').click(function(){
	    		if ($('.top-menu').is(':hidden')) {
	    			$('.top-menu').fadeIn('fast')
	    			
	    		} else {
	    			
	    			$('.top-menu').fadeOut('fast', function() {
	    				$('.submenu').remove();							
	    			});
	    		}
	        	
	        });

		    	// Call projects items
				$('#projectDropdown').click(function(e){
			
					var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
					$('body').append(preloader).show();

					var path = "/projects";
					if (!screenSize.isSmallScreen()){
						var mib = $('<div class="more-info-box project-dropdown-js"><span class="close-btn"></span><h3>Builders shorcut</h3><div id="content1"></div></div>');
						$(mib).insertAfter($(this));
					} else if ($('.submenu').length) {
						$('.submenu').slideUp('fast', function(){
							$('.submenu').remove();							
						});
					}
					$.get(path)
					.done(function(data) {
						var $response=$(data);
						$('#bowlG').remove();

						// not smartphone or tablet
						if (!screenSize.isSmallScreen()){

							var fw = $($response).find('.tablesorter-js');
							$(fw).appendTo($('#content1'));
							
							$('.tablesorter-js', mib).removeClass('tablesorter')

							$('.top-menu .shortcut-js .scLink').each(function(){
								var scLink = $(this).attr('data-sc');
								$(this).attr('href', scLink);
							});
							
							$(mib).slideDown('fast');
						} else { // show the menu

							var fw = $($response).find('.scLink');
							$('<ul/>').addClass('submenu').appendTo('.project-dropdown');
							$(fw).each(function(){
								var scLink = $(this).attr('data-sc');
								$(this).attr('href', scLink);
								var $li = $('<li>').append($(this));
								$('.submenu').append($li);
							});
							$('.submenu').slideDown('fast');
						}
						
						// remove the submenu for smartphone or tablets
						if (!screenSize.isSmallScreen()){
							
							$('.submenu').remove();	
						
							// close popup or menu	
							helpers.closePopup(mib, 'slideUp');
						} 
							
					});

				});
			}
	    };

    return projectDropDown;
});