define(['jquery', 'helpers'], function ($, helpers) {
	 "use strict";
    var realtimePages;
    
    realtimePages = {
        buildDetail: function (m, jsonFeed) {
        	
            try {
            	
                  var obj = JSON.parse(m);
                  
                  $.each(obj, function (key, value) {
                  	
                  	// update timing table
                  	var startTime = value.times[0]
                  	var endTime = value.times[1]

                  	if (!endTime) { 
	                  	//console.log(startTime, endTime)

	                  	$('.start-time-js').text(helpers.timeConverter(startTime));
	                    $('.end-time-js').text(helpers.timeConverter(endTime));
	                    $('.elapsed-time-js').text(helpers.getTime(startTime, endTime));
	                    var currentStepArray = [];

	                    //console.log(value.currentStep)


	                    /*
	                    $.each(value.currentStep, function (key, value) {
	                    	i = ++i
	                    	if (key === "times") {
	                    		console.log(value[0]);
	                    		currentStepArray.push(key, value)
	                    		$('.update-time-js', stepList).eq(i -1).html(getTime(startTime, endTime));
	                    	}
	                    });
						//console.log(currentStepArray)
	                    */
	                    var i = 0

	                  	$.each(value.steps, function (key, value) {
	                  			
	                  		 var isStarted = value.isStarted;
	                  		 var isFinished = value.isFinished;
	                  		 var isRunning = isStarted && !isFinished;
	                  		 var startTime = value.times[0];
	                  		 var endTime = value.times[1];
	                  		 var resultsClass = helpers.getResult(value.results[0]);

	                  		if (!value.hidden) {
	                  			i = ++i;
	                  			
	                  			// update step list
	                  			$.each(value.logs, function (key, value) {
	                  				var logText = value[0];
	                  				var logUrl = value[1];		
	                  				$('.s-logs-js a', window.stepList).eq(i -1).text(logText);	
	                  				$('.s-logs-js a', window.stepList).eq(i -1).attr('href', logUrl);	
	                  			});
	              				
	              				if (isRunning) {
	          						$('.update-time-js', window.stepList).eq(i -1).html(helpers.getTime(startTime, endTime));
	          						$('.s-text-js', window.stepList).eq(i -1).html(value.text.join(' '));
	              				}
	              				
	              				if (isRunning) {	
	              					$('.s-result-js', window.stepList).eq(i -1).removeClass().addClass('running result s-result-js');	
	              				} else if (isFinished) {
	              					$('.s-result-js', window.stepList).eq(i -1).removeClass().addClass(resultsClass + ' result s-result-js');		
	              				}
	              				
	              			}
	              			
	                  	});
						}
	                });
					
          		}
               
            catch(err) {
            }
		            
        },
        frontPage: function(m){
        	function sumVal(arr) {
	          var sum = 0;
	          $.each(arr,function(){
	            sum+=parseFloat(this) || 0;
	          });
	          return sum;
			};
        	try {
            	
	          var obj = JSON.parse(m);
	          
	          var arrayPending = [];
	            
	          $.each(obj.builders, function (key, value) {
	          	console.log(m)
	          	arrayPending.push(value.pendingBuilds);
	          });
	          
	          $('#pendingBuilds').html(sumVal(arrayPending));

	          var arraySlaves = [];
	          
	          $.each(obj.slaves, function (key) {
	            arraySlaves.push(key);
	          });

	          $('#slavesNr').html(arraySlaves.length);
          		
            }
            catch(err) {
            }
        }
    }
    return realtimePages
});