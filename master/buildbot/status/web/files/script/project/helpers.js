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
			
		// specific for the builddetail page
		}, startTimer: function(el, start) {		
			
			 var start = start,
		     cDisplay = $(el);
		
		     var format = function(t) {
			 var hours = Math.floor(t / 3600),
		        minutes = Math.floor(t / 60 % 60),
		        seconds = Math.floor(t % 60),
		        arr = [];
		   
		         if (hours > 0) {
				    arr.push(hours == 1 ? '1 hr' : hours + 'hrs');
				 }
				 if (minutes > 0 || hours > 0) {
				    arr.push(minutes > 1 ? minutes + ' mins' : minutes + ' min');
				 }
				 if (seconds > 0 || minutes > 0 || hours > 0) {
				    arr.push(seconds > 1 ? seconds + ' secs' : seconds + ' sec');
				 }
				cDisplay.html(arr.join(' '));
		     };
		    
		   format(new Date().getTime() / 1000 - start); 	

		// display time between two timestamps	
		}, getTime: function  (start, end) {
	
			if (end === null) {
				end = Math.round(+new Date()/1000);	
			}

			var time = end - start;	

			var getTime = Math.round(time)
			var hours = Math.floor(time / 3600) == 0? '' : Math.floor(time / 3600) + ' hours ' ;
			
			var minutes = Math.floor(getTime / 60) == 0? '' : Math.floor(getTime / 60) + ' mins, ';
			var seconds = getTime - Math.floor(getTime / 60) * 60 + ' secs ';
			return hours + minutes + seconds;

		}, getResult: function (resultIndex) {
        		
    		var results = ["success", "warnings", "failure", "skipped", "exception", "retry", "canceled"];
    		return results[resultIndex]
        }, getJsonUrl: function () {

    		var currentUrl = document.URL;
			               	
		    var parser = document.createElement('a');
		    parser.href = currentUrl;
		     
		    parser.protocol; // => "http:"
		    parser.hostname; // => "example.com"
		    parser.port;     // => "3000"
		    parser.pathname; // => "/pathname/"
		    parser.search;   // => "?search=test"
		    parser.hash;     // => "#hash"
		    parser.host;     // => "example.com:3000"

		    var buildersPath = parser.pathname.match(/\/builders\/([^\/]+)/);
		    var buildPath = parser.pathname.match(/\/builds\/([^\/]+)/);

		    
			if (helpers.getCurrentPage() === '#builders_page') {
				var fullUrl = parser.protocol + '//' + parser.host + '/json/builders/';
			}

		    if (helpers.getCurrentPage() === '#builddetail_page') {

		    	var fullUrl = parser.protocol + '//' + parser.host + '/json/builders/'+ buildersPath[1] +'/builds?select='+ buildPath[1] +'/';
		    }
		    
		    return fullUrl;
        }, getCurrentPage: function (isRealTime) {
        	//var currentPage = [$('#builders_page'),$('#builddetail_page'),$('#buildqueue_page'),$('#buildslaves_page')];
        	var currentPage = [$('#builddetail_page')];
        	var isRealTimePage = false;

        	$.each(currentPage, function(key, value) {
        		if (value.length === 1) {
        			isRealTimePage = true;
        			currentPage = value;
        		}
			});
			
        	if (isRealTime) {
				return isRealTimePage;
			} else {
				return currentPage.selector;
			}
        }
    };

    return helpers;
});
