define(['jquery', 'helpers'], function ($, helpers) {
	 "use strict";
    var realtimePages;
    
    realtimePages = {
        buildDetail: function (m, stepList) {
        	
            try {
        	
                  var obj = JSON.parse(m);
                  
                 $.each(obj, function (key, value) {
                  	
                  	// update timing table
                  	var startTime = value.times[0];
                  	var endTime = value.times[1];
 					
                  	var resultTxt = value.text;	
            		console.log(m)        	
                  			// timetable
		                    var myInt = setInterval(function() {
						    	helpers.startTimer($('#elapsedTimeJs'), startTime);
						    },1000);

							if (endTime) { 
								// If the build is finished
								clearInterval(myInt);        
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
		                  						$('.logs-txt',stepList).eq(i-1).text('Logs');
					                  			$.each(value.logs, function (key, value) {
					                  				var logText = value[0];
					                  				var logUrl = value[1];
					                  				logList += '<li class="s-logs-js"><a href='+ logUrl +'>'+ logText +'</a></li>';	
					                  			});
					                  			$('.log-list-js',stepList).eq(i-1).html(logList);
				                  			}
											// loop through urls
											if (hasUrls) {
					                  			var urlList = '';  
												$.each(value.urls, function (key, value) {
													 urlList += '<li class="urls-mod log-list-'+ helpers.getResult(value.results) +'"><a href="'+ value.url +'">'+ key +'</a></li>'; 
												});				                  			
					                  			$('.log-list-js',stepList).eq(i-1).append(urlList);
				                  			}

				                  			//Running text
			                  				
			                  				$('.update-time-js',stepList).eq(i-1).html('Running');
			                  				

			                  				// update build text
		          							$('.s-text-js',stepList).eq(i-1).html(value.text.join(' '));
		          							// update result class
			          						$('.s-result-js',stepList).eq(i-1).removeClass().addClass('running result s-result-js');	
			          						$(stepList).eq(i-1).removeClass().addClass('status-running');
			          						
			              				} else if (isFinished) {
			              					
			              					// Apply the updates from the finished state before applying finished class
			              					
			              					$('.update-time-js',stepList).eq(i-1).html(helpers.getTime(startTime, endTime));
			              					$('.s-result-js',stepList).eq(i-1).removeClass().addClass(resultsClass + ' result s-result-js');					              							              					
			              					$(stepList).eq(i-1).removeClass().addClass('finished status-'+resultsClass);
			              					
			              				}
			              				
		              				
		              			}
		              			
		                  	});

	                });
				
          		}
             
	            catch(err) {
	            	//console.log(err);
	            }
		           
        },
        buildersPage: function(m, tableRowList) {
			
		  	try {   
		  	//console.log(tableRowList)         	
	          	var obj = JSON.parse(m);  
	          	var i = 0;
	             $.each(obj, function (key, value) {
	          //   	
	             	if (value.project === "All Branches") {
	             	i = ++i;
	             	
	             	//var bNameTxt = $('.bname-js', tableRowList).text();
	             	//var trimmed = bNameTxt.trim();
	             	//console.log(bNameTxt)	             	
	             	
		             	tableRowList.each(function(){
		            		console.log($(this)) 		
		             		if (key === $('.bname-js',this).text().trim() && value.pendingBuilds) {
		             			//console.log($(this).text().trim());
		             			$('.current-cont',this).html('<a class="more-info popup-btn-js mod-1" data-rt_update="pending" href="#" data-in="'+ (i -1) +'"> Pending jobs </a>');
		             				//$('.current-cont',this).html(value.pendingBuilds);
		             		}
		             	});
		             	
	             	}
	             	/*
	             	if (value.pendingBuilds) {
	             		//console.log($('.bname-js', tableRowList))
	             		if (!$('.current-cont a', tableRowList).eq(i-1).hasClass('popup-btn-js')) {
	             			$('.current-cont', tableRowList).eq(i-1).html('<a class="more-info popup-btn-js mod-1" data-rt_update="pending" href="#" data-in="'+ (i -1) +'"> Pending jobs </a>');	
	             		} 
	             		
	             		//$('.current-cont', tableRowList).eq(i-1).removeClass();
	             	} else if (!$('.current-cont span', tableRowList).eq(i-1).hasClass('small-txt')) {
	             		
	             		$('.current-cont', tableRowList).eq(i-1).html('<span class="small-txt"> No jobs </span>');	             			
	             	}
	             	*/
	             	
	        		//console.log(value.project);     	
	             });
	        }
	           catch(err) {
	        	//console.log(err);
	        }
        },
        frontPage: function(m){
        	console.log('frontpage');
        	function sumVal(arr) {
	          var sum = 0;
	          $.each(arr,function() {
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