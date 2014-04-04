define(['screensize','text!templates/popups.mustache', 'mustache'], function (screenSize,popups,Mustache) {

    "use strict";
    var helpers;

    var css_classes = {SUCCESS: "success",
        WARNINGS: "warnings",
        FAILURE: "failure",
        SKIPPED: "skipped",
        EXCEPTION: "exception",
        RETRY: "retry",
        CANCELED: "exception",
        RUNNING: "running",
        NOT_STARTED: "not_started",
        None: ""
    };

    String.prototype.format = function () {
        var args = arguments;
        return this.replace(/{(\d+)}/g, function (match, number) {
            return typeof args[number] != 'undefined' ? args[number] : match;
        });
    };

    Number.prototype.clamp = function(min, max) {
      return Math.min(Math.max(this, min), max);
    };
    
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

			// Set the currentmenu item
			helpers.setCurrentItem();

			// Authorize on every page
			helpers.authorizeUser();

			if ($('#buildslave_page').length) {
				// display the number of current jobs
				helpers.displaySum($('#currentJobs'),$('#runningBuilds_onBuildslave').find('li'));
			}			

			if ($('#builddetail_page').length > 0) {
				helpers.summaryArtifactTests();
			}

			if ($('#tb-root').length != 0) {
                //Disabled until we decided that we need an updating front page
				//helpers.updateBuilders();
			}

			if ($('#builder_page').length != 0) {				
				helpers.codeBaseBranchOverview($('#brancOverViewCont'));
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
				var is_chrome = /chrome/.test( navigator.userAgent.toLowerCase());
				var isWindows = navigator.platform.toUpperCase().indexOf('WIN')!==-1;
				if (is_chrome) {
					$('body').addClass('chrome');
				}
				if (isWindows) {
					$('body').addClass('win');
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
		
			$('#authUserBtn').click(function(){
				helpers.eraseCookie('fullName1','','eraseCookie');				
			});
			helpers.tooltip($('.tooltip'));

		}, tooltip: function (el) {
			
			el.hover(function(e) {
				var toolTipCont = $('<div class="tooltip-cont" />');
				this.t = this.title;
				this.title = "";
				var cursorPosTop = e.pageY + 5;
				var cursorPosLeft = e.pageX + 5;
				$(e.target).click(function(){
					toolTipCont.remove();					
				});	
				toolTipCont.html(this.t)
				.appendTo('body')
				.css({'top':cursorPosTop,'left':cursorPosLeft})				
				.fadeIn('fast');
				
			}, function() {
				this.title = this.t;
				var toolTipCont = $('.tooltip-cont');	
				toolTipCont.fadeOut('fast', function(){					
					$(this).remove();
				});
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


		}, setCurrentItem: function () {
			
				var path = window.location.pathname.split("\/");
				
				 $('.top-menu a').each(function(index) {
				 	var thishref = this.href.split("\/");
				 	
				    if(this.id == path[1].trim().toLowerCase() || (this.id == 'home' && path[1].trim().toLowerCase().length === 0))
				        $(this).parent().addClass("selected");
				});
		
		}, jCenter: function(el) {
				var h = $(window).height();
			    var w = $(window).width();
			    var tu = el.outerHeight(); 
			    var tw = el.outerWidth(); 			   			    

			    // adjust height to browser height , "height":h - 75 , "height":'auto'
			    
			    if (h < (tu + 5)) {

			    	el.css({"top": 5 + $(window).scrollTop() + "px","height":h -60});
			    } else {
			    
			    	el.css({"top": (h - tu) / 2 + $(window).scrollTop() + 'px',"height":'auto'});
			    }
				
				el.css("left", (w - tw) / 2 + $(window).scrollLeft() + "px");
				return el;
			
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
			$('#tablesorterRt').delegate('.run-build-js', 'click', function(e){			
				$('.remove-js').remove();
				e.preventDefault();
                var prevElem = $(this).prev();
				var datab = prevElem.attr('data-b');
				var dataindexb = prevElem.attr('data-indexb');
                var dataReturnPage = prevElem.attr('data-returnpage');
				var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
                var builder_name = $(this).prev().attr('data-b_name');
				$('body').append(preloader).show();
				// get the current url with parameters append the form to the DOM and submit it
                var url = location.protocol + "//" + location.host + "/forms/forceBuild";

                //get all branches
                var urlParams = {rt_update: 'extforms', datab: datab, dataindexb: dataindexb, builder_name: builder_name, returnpage: dataReturnPage};
                urlParams = helpers.codebasesFromURL(urlParams);

				$.get(url, urlParams, "json").done(function(data, textStatus, jqXHR) {
					$('#bowlG').remove();
					var formContainer = $('<div/>').attr('id', 'formCont').append($(data)).appendTo('body').hide();
                    // Add the value from the cookie to the disabled and hidden field
                    helpers.setFullName($("#usernameDisabled, #usernameHidden", formContainer));

                    var form = formContainer.find('form').ajaxForm();

                    $(form).ajaxSubmit(function(data) {
                        requirejs(['realtimePages'], function (realtimePages) {
                            var name = dataReturnPage.replace("_json", "");
                            realtimePages.updateSingleRealTimeData(name, data);
                        });
                    });
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
					
			var mustacheTmpl = Mustache.render(popups, {'preloader':'true'});
			var preloader = $(mustacheTmpl);	

			var selectAll = $('#selectall');
			
			selectAll.click(function () {
				var tableSorter = $('#tablesorterRt').dataTable();							   				
				var tableNodes = tableSorter.fnGetNodes();	
		        $('.fi-js',tableNodes).prop('checked', this.checked);
		    });

			function ajaxPost(str) {					
				$('body').append(preloader).show();					
				var tableSorter = $('#tablesorterRt').dataTable();							   				
				str = str+'&ajax=true';
				
				$.ajax({
					type: "POST",
					url: 'buildqueue/_selected/cancelselected',
					data: str,
					success: function (data) {
						preloader.remove();
						tableSorter.fnClearTable();
						$.each(data, function (key, value) {
		          			var arObjData = [value];
							tableSorter.fnAddData(arObjData);							
						});
						selectAll.prop('checked',false);
					}
				});
				return false;									
			}				

			$('#submitBtn').click(function(e){					
				e.preventDefault();
				
				var tableSorter = $('#tablesorterRt').dataTable();							   				
				var tableNodes = tableSorter.fnGetNodes();	
		        var checkedNodes = $('.fi-js',tableNodes);
		        
		        var formStr = "";
		        checkedNodes.each(function(){
		        	if ($(this).is(':checked')) {
		        		formStr += 'cancelselected='+$(this).val()+'&';
		        	}		        	
		        });
		        var formStringSliced = formStr.slice(0,-1);		        
		        
				if (formStringSliced != '') {
					ajaxPost(formStringSliced);				
				}				
			});
			$('#tablesorterRt').delegate('.force-individual-js', 'click', function(e){					
				e.preventDefault();
				var iVal = $(this).prev().prev().val();
				var str = 'cancelselected='+iVal;								
				ajaxPost(str);						
			});
			
		}, updateBuilders: function () {
			$.ajax({
				url: "/json/builders/?filter=0",
				dataType: "json",
				type: "GET",
				cache: false,
				success: function (data) {
                    var arrayBuilders = [];
                    var arrayPending = [];
                    var arrayCurrent = [];
                    $.each(data, function (key, value) {
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
                    }

                    $('#pendingBuilds').text(sumVal(arrayPending));
                }
            });

            $.ajax({
				url: "/json/slaves/?filter=0",
				dataType: "json",
				type: "GET",
				cache: false,
				success: function (data) {
                    var arraySlaves = [];
                    $.each(data, function (key) {
                        arraySlaves.push(key);
                    });

                    $('#slavesNr').text(arraySlaves.length);
				}
			});
		}, codeBaseBranchOverview: function(El) {
	        	
    		var decodedUri = decodeURIComponent(window.location.search);
			var parsedUrl = decodedUri.split('&');
			var cbTable = $('<div class="border-table-holder"><div id="overScrollJS" class="inner-table-holder">'+
							'<table class="codebase-branch-table"><tr class="codebase"><th>Codebase'+
							'</th></tr><tr class="branch"><th>Branch</th></tr></table></div></div>');
		
  			cbTable.appendTo(El);

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
		}, displaySum: function (displayEl, countEl) {
			// Insert the total length of the elements
			displayEl.text(countEl.length);

		}, summaryArtifactTests: function () { // for the builddetailpage. Puts the artifacts and testresuts on top
			
			// Artifacts produced in the buildsteplist
			var artifactJS = $('li.artifact-js').clone();
			
			// Link to hold the number of artifacts
			var showArtifactsJS = $('#showArtifactsJS');
			var noArtifactsJS = $('#noArtifactsJS');

			// update the popup container if there are artifacts
			if (artifactJS.length > 0) {
                noArtifactsJS.html("");
                
				showArtifactsJS
				.show()				
				.text('(' + artifactJS.length + ') Artifacts ')
				.next()
				.find('.builders-list')
				.append(artifactJS);				
			} else {
				noArtifactsJS.show();								
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
			var expiredate = eraseCookie === undefined? expiry.toGMTString() : 'Thu, 01 Jan 1970 00:00:00 GMT;';
			
			document.cookie=name + "=" + escape(value) + "; path=/; expires=" + expiredate; 
			
		}, startCounter: function(el, myStartTimestamp) { 
			var startTimestamp = parseInt(myStartTimestamp);			    
		    var end = Math.round(+new Date()/1000);	
		    var time = end - startTimestamp;	
			var getTime = Math.round(time);
			function timeVars() {
			var 
				days = Math.floor(getTime / 86400),
				hours = Math.floor(getTime / 3600) % 24,
		        minutes = Math.floor(getTime / 60 % 60),
		        seconds = Math.floor(getTime % 60),
		        arr = [];
		   		 if (days > 0) {
				    arr.push(days == 1 ? '1 day ' : days + ' days');
				 }
		         if (hours > 0) {
				    arr.push(hours == 1 ? '1 hr ' : hours + ' hrs');
				 }
				 if (minutes > 0 || hours > 0) {
				    arr.push(minutes > 1 ? minutes + ' mins' : minutes + ' min');
				 }
				 if (seconds > 0 || minutes > 0 || hours > 0) {
				    arr.push(seconds > 1 ? seconds + ' secs' : seconds + ' sec');
				 }
				 el.html(arr.join(' '));
			}
			timeVars();
			(function repeatTimeout(){
				getTime++;
				timeVars();
				setTimeout(repeatTimeout, 1000);			 
			})();		    	
        }, inDOM: function(element) {
            return element.closest(document.documentElement).size() > 0;
		}, delegateToProgressBar: function (bars) {
            $.each(bars, function(key, elem) {
                var obj = $(elem);
                helpers.progressBar(obj.attr('data-etatime'),obj,obj.attr('data-starttime'));
            });

		}, verticalProgressBar: function(el,per) {
			// must be replaced with json values
			el.height("{0}%".format(per));

		}, progressBar: function(etaTime, el, startTime, overTime) {
			var start = moment.unix(startTime),
			percentInner = el.children('.percent-inner-js'),
			timeTxt = el.children('.time-txt-js');
            var hasETA = etaTime > 0;

			if (overTime) {
				el.addClass('overtime');
			}

			function timeVars() {
                var percent = 100;
                var old_lang = moment.lang();

                if (hasETA) {
                    var now = moment(),
                    addSubtract = overTime === undefined? etaTime-- : etaTime++,
                    then = moment().add('s',addSubtract),
                    etaEpoch = now + (etaTime * 1000.0);

                    percent = 100 - (then - now) / (then - start) * 100;
                    percent = percent.clamp(0,100);

                    moment.lang('progress-bar-en');
                    timeTxt.html(moment(etaEpoch).fromNow());

                    if (now > etaEpoch)
                        el.addClass('overtime');
                }
                else {
                    moment.lang('progress-bar-no-eta-en');
                    timeTxt.html(moment(parseInt(startTime * 1000)).fromNow());
                }

                //Reset language to original
                moment.lang(old_lang);
                percentInner.css('width',percent + "%");
			}
			timeVars();

			(function repeatTimeout() {	 
	        	timeVars();
                setTimeout(function(){
                    if (helpers.inDOM(percentInner)) {
                        repeatTimeout()
                    }
                }, 1000);
			})();
		}, startCounterTimeago: function(el, myStartTimestamp) {
			function timeVars() {
				var startTimestamp = parseInt(myStartTimestamp);			    		    
				var lastMessageTimeAgo = moment.unix(startTimestamp).fromNow();							
				el.html(lastMessageTimeAgo);	
			}
			timeVars();		    
		    (function repeatTimeout(){
		    	timeVars();
		    	setTimeout(function() {
                    if (helpers.inDOM(el)) {
                        repeatTimeout();
                    }
                }, 1000);
		    })()
		}, getTime: function  (start, end) {
	
			if (end === null) {
				end = Math.round(+new Date()/1000);	
			}

			var time = end - start;	

			var getTime = Math.round(time);
			var days = Math.floor(time / 86400) == 0? '' : Math.floor(time / 86400) + ' days ' ;
			var hours = Math.floor(time / 3600) == 0? '' : Math.floor(time / 3600) % 24 + ' hours ';
			
			var minutes = Math.floor(getTime / 60) == 0? '' : Math.floor(getTime / 60) % 60+ ' mins, ';
			var seconds = getTime - Math.floor(getTime / 60) * 60 + ' secs ';
			return days + hours + minutes + seconds;

		}, getResult: function (resultIndex) {
        		
    		var results = ["success", "warnings", "failure", "skipped", "exception", "retry", "canceled"];
    		return results[resultIndex]
        
        }, getSlavesResult: function (connected, runningBuilds) {

            return connected === false ? 'Not connected' : runningBuilds.length > 0 ? 'Running' : 'idle';

        }, getClassName: function(connected, runningBuilds) {
        	
			var slavesResult = helpers.getSlavesResult(connected, runningBuilds);

            return slavesResult === 'Not connected' ? 'status-td offline' : slavesResult === 'Running' ? 'status-td building' : 'status-td idle';

        }, getCurrentPage: function () {
        	var currentPage = document.getElementsByTagName('body')[0].id;
        	// return the id of the page        
			return currentPage;			
			 
		}, hasfinished: function () {
			var hasfinished = false;
			var isFinishedAttr = $('#isFinished').attr('data-isfinished');
			
			if (isFinishedAttr === undefined) {
				hasfinished = false;
        	}

        	if (isFinishedAttr === true) {
				hasfinished = true;
        	}

        	return hasfinished

		}, isRealTimePage: function() {
			var isRealtimePage = false
			var currentRtPages = ['buildslaves_page','builders_page','builddetail_page','buildqueue_page'];
			var current = helpers.getCurrentPage();
			$.each(currentRtPages, function(key,value) {
				if (value === current) {
					isRealtimePage = true;
				}
			});
			return isRealtimePage;
			
		}, getCookie: function (name) { // get cookie values
		  	var re = new RegExp(name + "=([^;]+)"); 
		  	var value = re.exec(document.cookie); 
		  	return (value != null) ?  decodeURI(value[1]) : ''; 

		}, eraseCookie: function (name, value, eraseCookie) {
    		helpers.setCookie(name, value, eraseCookie);

		}, closePopup: function(boxElement, clearEl) {
			
			var closeBtn = $('.close-btn').add(document);
			
			closeBtn.bind('click touchstart', function(e){
				
				if ((!$(e.target).closest(boxElement).length || $(e.target).closest('.close-btn').length)) {					
				
						if (clearEl === undefined ) {

							boxElement.remove();
						} else {
							boxElement.slideUp('fast', function(){
								$(this).remove();	
							});
						}

					$(this).unbind(e);
				
				}

			});	
		}, codebasesFromURL: function (urlParams) {
            var sPageURL = window.location.search.substring(1);
            var sURLVariables = sPageURL.split('&');
            $.each(sURLVariables, function(index, val) {
                var sParameterName = val.split('=');
                if (sParameterName[0].indexOf("_branch") >= 0) {
                    urlParams[sParameterName[0]] = sParameterName[1];
                }
            });

            return urlParams;
        },
        urlParamsToString: function (urlParams) {
            var ret = [];
            $.each(urlParams, function (name, value) {
                ret.push(name + "=" + value);
            });

            return ret.join("&");
        },
        getCssClassFromStatus: function(status) {
            var values = Object.keys(css_classes).map(function (key) {
                return css_classes[key];
            });
            return values[status];
        }
	};

    return helpers;
});
