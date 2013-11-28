define(['jquery', 'screensize'], function ($, screenSize) {

    "use strict";
    var helpers;
    
    helpers = {
        init: function () {

        	if ($('.builders_page').length && window.location.search != '') {
        		// Parse the url and insert current codebases and branches
        		
	        	(function( $ ) {
	        		
	        		var decodedUri = decodeURIComponent(window.location.search);

					var parsedUrl = decodedUri.split('&')

					var cbTable = $('<div class="border-table-holder">'+
									'<table class="codebase-branch-table"><tr class="codebase"><th>Codebase'+
									'</th></tr><tr class="branch"><th>Branch</th></tr></table></div>');
				
          			$(cbTable).appendTo($('.filter-table-input'));

					$(parsedUrl).each(function(i){

						// split key an value
						var eqSplit = this.split( "=");

						if (eqSplit[0].indexOf('_branch') > 0) {
								
							// seperate branch and 
							var codeBases = this.split('_branch')[0];
							if (i == 0) {
								codeBases = this.replace('?', '').split('_branch')[0];
							}

							var branches = this.split('=')[1];

							$('tr.codebase').append('<td>' + codeBases + '</td>');
							$('tr.branch').append('<td>' + branches + '</td>');
						}
						
					});
				})( jQuery );
			}

		
			

			/*
				// only for testing		
				$('<div/>').addClass('windowsize').css({'position': 'absolute', 'fontSize': '20px'}).prependTo('body');

				var ws = $(window).width() + ' ' +  $(window).height();

				$('.windowsize').html(ws);
				    	
			    $(window).resize(function(event) {
			    	ws = $(window).width() + ' ' +  $(window).height();
			    	$('.windowsize').html(ws);
			    });
			*/

			if ($('#tb-root').length != 0) {
				$.ajax({
					url: "/json?filter=0",
					dataType: "json",
					type: "GET",
					cache: false,
					success: function (data) {
					var arrayBuilders = [];
					var arrayPending = [];
					var arrayCurrent = [];
					$.each(data.builders, function (key, value) {
					arrayBuilders.push(key);
					arrayPending.push(value.pendingBuilds);
					if (value.state == 'building') {
					arrayCurrent.push(value.currentBuilds);
					}
					});

					function sumVal(arr) {
					var sum = 0;
					$.each(arr,function(){sum+=parseFloat(this) || 0;});
					return sum;
					};
					var arraySlaves = [];
					$.each(data.slaves, function (key) {
					arraySlaves.push(key);
					});

					var arrayProjects = [];
					$.each(data.project, function (key) {
					arrayProjects.push(key);
					});
					
					$('#slavesNr').text(arraySlaves.length);
					$('#pendingBuilds').text(sumVal(arrayPending));
					
					}
				});
			}
			
        // submenu overflow on small screens
        


	        var isMediumScreen = screenSize.isMediumScreen();
	                
	        function menuItemWidth() {
	        	
	        	if (isMediumScreen){	
		        	var wEl = 0;
		        	$('.breadcrumbs-nav li').each(function(){
			        	wEl += $(this).outerWidth();
			        });
			        $('.breadcrumbs-nav').width(wEl + 100);
		        } else {
		        	$('.breadcrumbs-nav').width('');	
		        }
		        
	        }
	        menuItemWidth();
			$(window).resize(function() {
				isMediumScreen = screenSize.isMediumScreen();
				menuItemWidth();			  
			});
			
			// check all in tables
			$(function selectAll() {
			    $('#selectall').click(function () {
			    	
			        $('.fi-js').prop('checked', this.checked);
			    });
			});
			$('.force-individual-js').click(function(e){
				e.preventDefault();
				/*
				$(this).prev('.fi-js').prop('checked', true);
				*/
				var iVal = $(this).prev().prev().val();
				
				var hi = $('<input checked="checked" name="cancelselected" type="hidden" value="'+  iVal  +'"  />');
				$(hi).insertAfter($(this));
				$('#formWrapper form').submit();

			});
			
			// chrome font problem fix
			$(function chromeWin() {
				var is_chrome = /chrome/.test( navigator.userAgent.toLowerCase() );
				var isWindows = navigator.platform.toUpperCase().indexOf('WIN')!==-1;
				if(is_chrome && isWindows){
				  $('body').addClass('chrome win');

				}
			});

			function toolTip(ellipsis) {
				$(ellipsis).parent().hover(function(){
					
					var txt = $(ellipsis, this).attr('data-txt');
					
					var toolTip = $('<div/>').addClass('tool-tip').text(txt);

					$(this).append($(toolTip).css({
						'top':$(ellipsis, this).position().top -10,
						'left':$(ellipsis, this).position().left - 20
					}).show());

				}, function(){
					$('.tool-tip').remove();
				});
				// ios fix
				$(document).bind('click touchstart', function(e){
					$('.tool-tip').remove();
					$(this).unbind(e);
				});

			}
				
			toolTip('.ellipsis-js');

			//parse reason string
			$('.codebases-list .reason-txt').each(function(){
				var rTxt = $(this).text().trim();
				if (rTxt === "A build was forced by '':") {
					$(this).remove();
				}
			});

			$('#submitBtn').click(function(){
				$('#formWrapper form').submit();
			});
			
			// run build with default parameters
			$('.run-build-js').click(function(e){
			
				$('.remove-js').remove();
				e.preventDefault();
				var datab = $(this).prev().attr('data-b');
				var dataindexb = $(this).prev().attr('data-indexb');
				var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
				$('body').append(preloader).show();
				$.get('', {rt_update: 'extforms', datab: datab, dataindexb: dataindexb}).done(function(data) {
					$('#bowlG').remove();
					$('<div/>').addClass('formCont').hide().appendTo('body')		
					$(data).appendTo('.formCont')
					$('.formCont .command_forcebuild .grey-btn').trigger('click');
				});
			});
	
		}
	};

    return helpers;
});
