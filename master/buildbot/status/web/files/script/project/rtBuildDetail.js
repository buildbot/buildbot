define(['jquery', 'realtimePages', 'helpers','popup','text!templates/builders.mustache','mustache'], function ($, realtimePages, helpers,popup,builders,Mustache) {
         "use strict";
    var rtBuildDetail;
    var stepList = $('#stepList > li');
    var currentstepJS = $('.current-step-js');

    rtBuildDetail = {
        init: function () {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions["build"] = rtBuildDetail.processBuildDetail
            realtimePages.initRealtime(realtimeFunctions);
        }, processBuildDetail: function(data) { 

        	 try {
                 $.each(data, function (key, value) {
                  	
                  	// update timing table
                  	var startTime = value.times[0];
                  	var endTime = value.times[1];
 					        

                    if (value.currentStep != null && value.currentStep != undefined) {                      
                      var currentStepEta = value.currentStep.eta;                      
                      $('.percent-outer-js').remove();
                      var mustacheTmpl = $(Mustache.render(builders, {progressBar:true,etaStart:startTime,etaCurrent:currentStepEta}))
                      .addClass('build-detail-progress')             
                      .insertAfter(currentstepJS);                      
                      helpers.delegateToProgressBar($('.percent-outer-js'));  
                    } 
                  	var resultTxt = value.text;	
            		    	
                  			// timetable
                  			helpers.startCounter($('#elapsedTimeJs'), startTime);

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
        }       	
    };

    return rtBuildDetail;
});