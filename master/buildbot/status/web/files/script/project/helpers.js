define(['jquery', 'screensize'], function ($, screenSize) {

    "use strict";
    var helpers;
    
    helpers = {
        init: function () {

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

			// Authorize on every page
			helpers.authorizeUser();

        	// insert codebase and branch on the builders page
        	if ($('#builders_page').length && window.location.search != '') {
        		// Parse the url and insert current codebases and branches
        		helpers.codeBaseBranchOverview();
			}

			if ($('#tb-root').length != 0) {
				helpers.updateBuilders();
			}
			
       		// submenu overflow on small screens

	        helpers.menuItemWidth(screenSize.isMediumScreen());
			$(window).resize(function() {
				helpers.menuItemWidth(screenSize.isMediumScreen());			  
			});
			
			// check all in tables and remove builds
			helpers.selectBuildsAction();
			
			// chrome font problem fix
			$(function chromeWin() {
				var is_chrome = /chrome/.test( navigator.userAgent.toLowerCase() );
				var isWindows = navigator.platform.toUpperCase().indexOf('WIN')!==-1;
				if(is_chrome && isWindows){
				  $('body').addClass('chrome win');

				}
			});

			// tooltip used on the builddetailpage
			helpers.toolTip('.ellipsis-js');

			// parse reason string on the buildqueue page
			helpers.parseReasonString();


			// trigger individual builds on the builders page
			helpers.runIndividualBuild();
			
			
			// Set the full name from a cookie. Used on buildersform and username in the header
			helpers.setFullName($("#buildForm .full-name-js, #authUserName"));			
		
			$('#authUserBtn').click(function(e){
				helpers.eraseCookie('fullName1','','eraseCookie');				
			});

		}, authorizeUser: function() {

			// the current url
			var url = window.location;
				
			// Does the url have 'user' and 'authorized' ? get the fullname
			if (url.search.match(/user=/) && url.search.match(/autorized=True/)) {				
				var fullNameLdap = decodeURIComponent(url.search.split('&').slice(0)[1].split('=')[1]);	
				// set the cookie with the full name on first visit
				helpers.setCookie("fullName1", fullNameLdap);
				window.location = "/";
			} else if (helpers.getCookie("fullName1") === '') {
				// Redirect to loginpage if missing namecookie
				window.location = "/login";
			} else {
				// Extend the expiration date
				helpers.setCookie("fullName1", helpers.getCookie("fullName1"));
			}

		}, setFullName: function(el) {			
			var valOrTxt;
			var cookieVal = helpers.getCookie("fullName1");

			// Loop through all elements that needs fullname 
			el.each(function(){
				// check if it is an input field or not
				valOrTxt = $(this).is('input')? 'val' : 'text';				
				$(this)[valOrTxt](cookieVal);
			});
			
		}, runIndividualBuild: function() { // trigger individual builds
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

					helpers.setFullName($("#usernameDisabled, #usernameHidden", formContainer));

					$('.command_forcebuild', formContainer).submit();
				});
			});			
			
		}, parseReasonString: function() { // parse reason string on the buildqueue page
				$('.codebases-list .reason-txt').each(function(){
					var rTxt = $(this).text().trim();
					if (rTxt === "A build was forced by '':") {
						$(this).remove();
					}
				});
			
		}, selectBuildsAction: function() { // check all in tables and perform remove action
			    $('#selectall').click(function () {			    	
			        $('.fi-js').prop('checked', this.checked);
			    });

			    // Submit the all the checkfields
				$('#submitBtn').click(function(){
					$('#formWrapper form').submit();
				});

			    // remove individual build
				$('.force-individual-js').click(function(e){
					e.preventDefault();					
					var iVal = $(this).prev().prev().val();
					
					var hi = $('<input checked="checked" name="cancelselected" type="hidden" value="'+  iVal  +'"  />');
					$(hi).insertAfter($(this));
					$('#formWrapper form').submit();
				});
			
		}, updateBuilders: function () {
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
		}, codeBaseBranchOverview: function() {
	        	
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
				
		}, menuItemWidth: function (isMediumScreen) { // set the width on the breadcrumbnavigation. For responsive use
	        	
        	if (isMediumScreen){	
	        	var wEl = 0;
	        	$('.breadcrumbs-nav li').each(function(){
		        	wEl += $(this).outerWidth();
		        });
		        $('.breadcrumbs-nav').width(wEl + 100);
	        } else {
	        	$('.breadcrumbs-nav').width('');	
	        }
		        
	    }, toolTip: function (ellipsis) { // tooltip used on the builddetailpage
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
		}, summaryArtifactTests: function () { // for the builddetailpage. Puts the artifacts and testresuts on top
			

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

		}, setCookie: function (name, value, eraseCookie) { // renew the expirationdate on the cookie

			var today = new Date(); var expiry = new Date(today.getTime() + 30 * 24 * 3600 * 1000); // plus 30 days 
			
			if (eraseCookie === undefined) {
				var expiredate = expiry.toGMTString();
			} else {
				var expiredate = 'Thu, 01 Jan 1970 00:00:00 GMT;';
			}
			//var expiredate = eraseCookie === undefined? expiry.toGMTString() : 'Thu, 01 Jan 1970 00:00:00 GMT;';
			
			document.cookie=name + "=" + escape(value) + "; path=/; expires=" + expiredate; 

		}, getCookie: function (name) { // get cookie values
		  	var re = new RegExp(name + "=([^;]+)"); 
		  	var value = re.exec(document.cookie); 
		  	return (value != null) ? unescape(value[1]) : ''; 
		}, eraseCookie: function (name, value, eraseCookie) {
    		helpers.setCookie(name, value, eraseCookie);
		}
	};

    return helpers;
});