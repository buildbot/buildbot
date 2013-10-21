define(['jquery', 'screensize'], function ($, screenSize) {

    "use strict";
    var projectDropDown;

    	projectDropDown = {
	        init: function () {
			var isSmallScreen = screenSize.isSmallScreen();
		    
			$(window).resize(function() {
				isSmallScreen = screenSize.isSmallScreen();
				if (isSmallScreen){	
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
					if (!isSmallScreen){
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
						if (!isSmallScreen){

							var fw = $($response).find('.tablesorter-js');
							$(fw).appendTo($('#content1'));
							
							$('.tablesorter-js', mib).removeClass('tablesorter')

							$('.top-menu .shortcut-js .scLink').each(function(){
								var scLink = $(this).attr('data-sc');
								$(this).attr('href', scLink);
							});
							
							$(mib).slideDown('fast');
						} else {

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
						
						if (!isSmallScreen){
							
							$('.submenu').remove();	
						
							// close popup or menu	
							$(document, '.close-btn').bind('click touchstart', function(e){

							    if (!$(e.target).closest(mib).length || $(e.target).closest('.close-btn').length) {
							        	
							        $(mib).slideUp('fast', function(){
							        	$(this).remove();	
							        });

							        $(this).unbind(e);
							    }
							});
						} 
							
					});

				});
			}
	    };

    return projectDropDown;
});