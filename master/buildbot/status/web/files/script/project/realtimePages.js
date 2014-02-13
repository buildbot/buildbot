define(['jquery','helpers','popup','text!templates/builders.html','mustache','livestamp'], function ($,helpers,popup,builders,Mustache) {
	 "use strict";
    var realtimePages;
    
    realtimePages = {
        buildDetail: function (m, stepList) {
        	var currentstepJS = $('.current-step-js');
            try {
        	
                  var obj = JSON.parse(m);
            		      
                 $.each(obj, function (key, value) {
                  	
                  	// update timing table
                  	var startTime = value.times[0];
                  	var endTime = value.times[1];
 					
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
        buildersPage: function(m, tableRowList) {
			
		  	try {   
		  	    	
	          	var obj = JSON.parse(m);  
	          	
		          	var i = 0;
	          		var objBuilder = obj.builders;
	          			          		
	          		$.each(objBuilder, function (key, value) {
	          			
	          			var item = $('[id="' + value.name + '"]');
	          			var currentCont = item.find('.current-cont');
	          			var pendingCont = item.find('.pending-cont');
	          			var jobsCont = item.find('.jobs-js');
	          			
	          			var lastRun = item.find('.last-build-js');
	          			var status = item.find('.status-build-js');
	          			 	          					
	          			if (value.pendingBuilds > 0) {	          				
	          				
	          				i = ++i;	          				
	          				var popupBtn = $(Mustache.render(builders, {'popupbtn':'true','number':i -1}));
								          				
	          				pendingCont
	          					.html(popupBtn)		             			
		    					.children(popupBtn).click(function(e){
		             				e.preventDefault();				        		             						             				
		             				popup.pendingJobs(popupBtn);						             				
		             			});

	          			} else {
	          				pendingCont.html('');
	          			}	          			
	          			
	             		if (value.currentBuilds.length > 0 ) {
	             				             		
	             			var htmlLi ='';
	             			
	             			var smHead = $('<h2 class="small-head">Current job</h2>');

	             			htmlLi = '<h2 class="small-head">Current job</h2><ul class="list current-job-js">';	             			
							
							var nameVal = '';
							var LiEl = '';

	             			$.each(value.currentBuilds, function (key, value) {	 
	             				
								$.each(value.currentStep, function (key, value) {
									if (key === 'name') {										
										nameVal = value; 		
									}									
								});	 
								htmlLi += Mustache.render(builders, {'li':{'name':nameVal, 'number':value.number,'url':value.url}});								
								
	             			});		             			
	             			
	             			htmlLi += '</ul>'
	             			currentCont.html(htmlLi);
	             			
	             		}
	             		if (value.pendingBuilds === 0 && value.currentBuilds.length === 0) {
		             		currentCont.html('<span class="small-txt"> No jobs </span>');
		             	} 
		             	
		             	if (value.latestBuild) {
			             	$.each(value.latestBuild, function (key, value) {		             			             		
			             		var buildUrl = status.find('.build-url-js')
			             		if (key === 'times') {

			             			//var lastMessageTimeAgo = moment().utc(value[1]).fromNow();	
			             			
			             			helpers.startCounterTimeago(lastRun.find('.last-run'), value[1])
			             			


			             			/*
			             			var time = helpers.getTime(value[0],value[1]).trim();		             					             			
			             			lastRun.find('.last-run').attr('data-livestamp',value[1]);		             						             			
			             			lastRun.find('.small-txt').html('('+ time +')');
			             			lastRun.find('.hidden-date-js').html(value[1]);			             			
			             			*/
			             		} 		        
			             		if (key === 'text') {		             					             		
			             			status.find('.hide-status-js, .status-text-js').text(value[0]);				             			
			             		}     		

			             		if (key === 'number') {
			             			buildUrl.text('#'+value)
			             		}

			             		if (key === 'url') {			             			
			             			buildUrl.attr('href',value);	
			             		}			             		
			             	});
		             	}
		             	
	          		});									
	        }
	           catch(err) {
	        	//console.log(err);
	        }
        }, rtBuildSlaves: function(m){
        		var tbsorter = $('.tablesorter-js').dataTable();        		
        		tbsorter.fnClearTable();        	
        	try {            		        
          		var obj = JSON.parse(m);  	          		          		          		
          		$.each(obj, function (key, value) { 
          			var arObjData = [value];										
					tbsorter.fnAddData(arObjData);	
          		});
            }
            catch(err) {
            }
        }, rtBuildqueue: function(m){
        		var tbsorter = $('.tablesorter-js').dataTable();        		
        		tbsorter.fnClearTable();
        	try {
				var obj = JSON.parse(m);								
				tbsorter.fnAddData(obj);														
            }
            catch(err) {
            }
        }
    }
    return realtimePages
});