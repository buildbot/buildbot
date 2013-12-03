define(['jquery', 'screensize'], function ($, screenSize) {

    "use strict";
    var helpers;
    
    helpers = {
        init: function () {

        	// insert codebase and branch on the builders page
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

						// split key and value
						var eqSplit = this.split( "=");

						if (eqSplit[0].indexOf('_branch') > 0) {
								
							// seperate branch
							var codeBases = this.split('_branch')[0];
							// remove the ? from the first codebase value
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

			// tooltip used on the builddetailpage
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
				// get the current url with parameters append the form to the DOM and submit it
				$.get('', {rt_update: 'extforms', datab: datab, dataindexb: dataindexb}).done(function(data) {
					$('#bowlG').remove();
					var formContainer = $('<div/>').attr('id', 'formCont').append($(data)).appendTo('body').hide();
					
					// Add the value from the cookie to the disabled and hidden field
					$("#usernameDisabled, #usernameHidden", formContainer)
					.val(helpers.getCookie("firstName") + ' ' + helpers.getCookie("lastName"));

					$('.command_forcebuild', formContainer).submit();
				});
			});			

		}, summaryArtifactTests: function () {
			// for the builddetailpage

			// Artifacts produced in the buildsteplist
			var artifactJS = $('li.artifact-js').clone();
			
			// Link to hold the number of artifacts
			var showArtifactsJS = $('#showArtifactsJS');

			// update the popup container if there are artifacts
			if (artifactJS.length > 0) {
				showArtifactsJS
				.removeClass('no-artifacts')
				.addClass('more-info mod-1 popup-btn-js-2')
				.text('(' + artifactJS.length + ') Artifacts ')
				.next()
				.find('.builders-list')
				.append(artifactJS);
			} else {
				showArtifactsJS.text('No Artifacts');
			}

			// Testreport and testresult
			var sLogs = $('.s-logs-js').clone();

			// Container to display the testresults
			var testlistResultJS = $('#testsListJS');

			var alist = [];
			
			$(sLogs).each(function() {	
				// filter the test results by xml and html file
				var str = $(this).text().split('.').pop();
				
				if (str === 'xml' || str === 'html') {
					alist.push($(this));
				}
			});
						
			// Show the testresultlinks in the top if there are any
			if (alist.length > 0) { 
				testlistResultJS.append($('<li>Test Results</li>'));
				testlistResultJS.append(alist);
			}
		}, setCookie: function (name, value) {
			var today = new Date(); var expiry = new Date(today.getTime() + 30 * 24 * 3600 * 1000); // plus 30 days 		
			document.cookie=name + "=" + escape(value) + "; path=/; expires=" + expiry.toGMTString(); 

		}, getCookie: function (name) { // get cookie values
		  	var re = new RegExp(name + "=([^;]+)"); 
		  	var value = re.exec(document.cookie); 
		  	return (value != null) ? unescape(value[1]) : ''; 
		}
	};

    return helpers;
});