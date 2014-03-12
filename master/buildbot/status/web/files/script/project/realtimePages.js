define(['jquery','helpers','popup','text!templates/builders.mustache','mustache'], function ($,helpers,popup,builders,Mustache) {
	 "use strict";
    var realtimePages;    
    var tbsorter = $('#tablesorterRt').dataTable();
    var stepList = $('#stepList > li');
    var currentstepJS = $('.current-step-js');
    var sock = null;
    var realTimeFunc = null;

    realtimePages = {
        createWebSocket: function(wsURI) {
            if (sock == null) {

                if ("WebSocket" in window) {
                    sock = new WebSocket(wsURI);
                } else if ("MozWebSocket" in window) {
                    sock = new MozWebSocket(wsURI);
                } else {
                    log("Browser does not support WebSocket!");
                    window.location = "http://autobahn.ws/unsupportedbrowser";
                }

                // if the socket connection is success
                if (sock) {
                     sock.onopen = function () {
                         $('#bowlG').remove();
                         // get the json url to parse
                         realtimePages.broadcastMessage(helpers.getJsonUrl());
                     };

                     // when the connection closes
                     sock.onclose = function(e) {
                         sock = null;
                         console.log("We lost our connection, retrying in 5 seconds...");
                         setTimeout(function() {realtimePages.createWebSocket(wsURI)}, 5000);
                     };

                     // when the client recieves a message
                     sock.onmessage = function(e) {
                         realtimePages.updateRealTimeData(e.data);
                     }
                }
            }

            return sock;
        },
        initRealtime: function (rtFunc) {
            realTimeFunc = rtFunc;

            //Attempt to load our table immediately
            var json = realtimePages.getInstantJSON();
            if (json !== undefined)
            {
                console.log("Loaded from instant JSON");
                realtimePages.updateRealTimeData(json);
            }

        	// Creating a new websocket
         	var wsURI = $('body').attr('data-realTimeServer');
            if (wsURI !== undefined && wsURI != "") {
                console.log(wsURI);
                realtimePages.createWebSocket(wsURI);
            }
            else {
                console.log("Realtime server not found, disabling realtime.")
            }
        },
        broadcastMessage: function(msg) {
            if (sock) {
                sock.send(msg);
            }
        },
        updateRealTimeData: function(data) {
            if (typeof data === "string") {
                data = JSON.parse(data);
            }
            realTimeFunc(data);
            console.log("Reloading data...")
        },
        getInstantJSON: function() {
            var script = $('#instant-json');
            if (script.length) {
                script.remove();
                return instantJSON;
            }
            return undefined;
        },
        rtBuildDetail: function (data,el) {
            
            try {
                 $.each(data, function (key, value) {
                  	
                  	// update timing table
                  	var startTime = value.times[0];
                  	var endTime = value.times[1];
 					          var currentStepEta = value.currentStep.eta;
                  	var resultTxt = value.text;	
            		    	
                  			// timetable
                  			helpers.startCounter($('#elapsedTimeJs'), startTime)
		                    

							if (endTime) { 
								// If the build is finished
								  
								// get the rest of the content
								if(!window.location.hash) {
							        window.location = window.location + '#finished';
							        window.location.reload();
									
								}
								sock.close();

							} 

							// build steps
		            var i = 0;
		            
                
                $('.percent-outer-js').remove();
                var mustacheTmpl = $(Mustache.render(builders, {progressBar:true,etaStart:startTime,etaCurrent:currentStepEta})).addClass('build-detail-progress');                
                mustacheTmpl.insertAfter(currentstepJS);
                helpers.delegateToProgressBar($('.percent-outer-js'));                

		            $.each(value.steps, function (key, value) {
		                  		
                		 var isStarted = value.isStarted;
                		 var isFinished = value.isFinished === true;
                		 var isRunning = isStarted && !isFinished;
                		 var startTime = value.times[0];
                		 var endTime = value.times[1];
                		 var resultsClass = helpers.getResult(value.results[0]);
                		 var isHidden = value.hidden === true;

                		 if (isHidden != true) {
                		 	
                			i = ++i;
                			 
                  		// update step list if it's not finished

                			if (isRunning) {
                					
              					// loop through the logs
              					
              					var hasLogs = value.logs.length > 0; 
              					var hasUrls = value.urls.length > 0; 
              					
              					if (hasLogs) {
              						
              						var logList = '';  
              						stepList.children('.logs-txt').eq(i-1).text('Logs');
                    			$.each(value.logs, function (key, value) {
                    				var logText = value[0];
                    				var logUrl = value[1];
                    				logList += '<li class="s-logs-js"><a href='+ logUrl +'>'+ logText +'</a></li>';	
                    			});
                    			stepList.children('.log-list-js').eq(i-1).html(logList);
                    	}
											// loop through urls
											if (hasUrls) {
                  			var urlList = '';  
												$.each(value.urls, function (key, value) {
													 urlList += '<li class="urls-mod log-list-'+ helpers.getResult(value.results) +'"><a href="'+ value.url +'">'+ key +'</a></li>'; 
												});				                  			
					              stepList.children('.log-list-js').eq(i-1).append(urlList);
				              }

	                  			//Running text                  				
                  				stepList.children('.update-time-js').eq(i-1).html('Running');                  				

                  				// update build text
	          							stepList.children('.s-text-js').eq(i-1).html(value.text.join(' '));

	          							// update result class
		          						stepList.children('.s-result-js').eq(i-1).removeClass().addClass('running result s-result-js');	
		          						stepList.eq(i-1).removeClass().addClass('status-running');
		          						
		          						currentstepJS.text(value.name);

                          
		          						
		          						
		              				} else if (isFinished) {
		              					
		              					// Apply the updates from the finished state before applying finished class
		              					
		              					stepList.children('.update-time-js').eq(i-1).html(helpers.getTime(startTime, endTime));
		              					stepList.children('.s-result-js').eq(i-1).removeClass().addClass(resultsClass + ' result s-result-js');					              							              					
		              					stepList.eq(i-1).removeClass().addClass('finished status-'+resultsClass);
		              					
		              				}
		              			}
		              			
		                });

	               });
				
          		}
	            catch(err) {
	            	//console.log(err);
	            }
		           
        },
        buildersPage: function(data) {		  	
    		tbsorter.fnClearTable();        

        	try {
          		tbsorter.fnAddData(data.builders);
	        }
	           catch(err) {
	        	//console.log(err);
	        }
        }, rtBuildSlaves: function(data){        		
        		tbsorter.fnClearTable();        	
        	try {
          		$.each(data, function (key, value) {
          			var arObjData = [value];
					tbsorter.fnAddData(arObjData);
          		});
            }
            catch(err) {
            }
        }, rtBuildqueue: function(data){        		
        		tbsorter.fnClearTable();
        	try {
				tbsorter.fnAddData(data);
				

            }
            catch(err) {
            }
        }
    };

    return realtimePages
});
