define(['jquery', 'helpers'], function ($, helpers) {
	 "use strict";
    var realtimePages;
    
    realtimePages = {
        buildDetail: function (m, jsonFeed) {

        		
            try {
            	
                  var obj = JSON.parse(m);
                  
                 $.each(obj, function (key, value) {
                  	
                  	// update timing table
                  	var startTime = value.times[0];
                  	var endTime = value.times[1];
                  	var stopRunning = $('.overall-result-js').hasClass('stopRunning-js');
                  	
                  	if (stopRunning) {
                  		sock.close();
                  	}
                  	
                  	var resultTxt = value.text;
                  		
                  		if (!stopRunning) { 

	                  		$('.overall-result-js').addClass(resultTxt).text(resultTxt);
	                  	
	                  	
		                  	//console.log(startTime, endTime)

		                  	$('.start-time-js').text(helpers.timeConverter(startTime));
		                    $('.end-time-js').text(helpers.timeConverter(endTime));
		                    $('.elapsed-time-js').text(helpers.getTime(startTime, endTime));
		                    

		                    //console.log(value.currentStep)


		                    /*
		                    var currentStepArray = [];
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
		                    var i = 0;
		                    
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
		                  			if (!helpers.getStepList(false, i).hasClass('finished')) {

		                  				if (isRunning) {
		                  					// loop through the logs
				                  			$.each(value.logs, function (key, value) {
				                  				var logText = value[0];
				                  				var logUrl = value[1];
				                  				helpers.getStepList('.log-list-js', i).empty().append('<li class="s-logs-js"><a href='+ logUrl +'>'+ logText +'</a></li>');;		
				                  				
				                  			});

			                  				helpers.getStepList('.update-time-js',i).html(helpers.getTime(startTime, endTime));
		          							helpers.getStepList('.s-text-js',i).html(value.text.join(' '));
			          						helpers.getStepList('.s-result-js',i).removeClass().addClass('running result s-result-js');	
			              				} else if (isFinished) {
			              					helpers.getStepList('.s-result-js',i).removeClass().addClass(resultsClass + ' result s-result-js');					              				
			              					helpers.getStepList(false, i).addClass('finished');
			              					
			              				}
			              				if (helpers.getStepList(false, i).hasClass('finished')) {
			              					console.log(helpers.getStepList(false, i));
			              				}
		              				}
		              			}
		              			
		                  	});
							if (endTime) { 
								$('.overall-result-js').addClass('stopRunning-js');
							}
							
							
							
						}
	                });
					
          		}
               
            catch(err) {
            	//console.log(err);
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