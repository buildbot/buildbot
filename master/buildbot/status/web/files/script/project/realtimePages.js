define(['jquery'], function ($) {
	 "use strict";
    var realtimePages;
    
    realtimePages = {
        buildDetail: function (m, jsonFeed) {

        	// The html list
        	var stepList = $('.step-list > li');

            function timeConverter(UNIX_timestamp){
				 var a = new Date(UNIX_timestamp*1000);
				 var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
			     var year = a.getFullYear();
			     var month = months[a.getMonth()];
			     var date = a.getDate();
			     var hour = a.getHours();
			     var min = a.getMinutes();
			     var sec = a.getSeconds();
			     var time = date+','+month+' '+year+' '+hour+':'+min+':'+sec ;
			     return time;
			}

			function getTime (start, end) {
				
				var time = start - end;
				var getTime = Math.round(time)
				return getTime;
			}
	            try {
	            	
	                  var obj = JSON.parse(m);
	                  			                  
	                  var arraytimes = [];
	                  var arrayText = [];
	                  var arrayIsFinished = [];
	                  var arrayLogs = [];
	                  var arrayLogsVal = [];
	                  var startTime = '';
	                  var endTime = '';

                      $.each(obj, function (key, value) {
                      		
                      	startTime = this.times[0]
                      	endTime = this.times[1]

                      	$(this.steps).each(function(){
                      			                  			          
                      		if (!this.hidden) {
	                  			if (this.times) {
	                  				arraytimes.push(this.times);
	                  			}
	                  			if (this.text) {
	                  				arrayText.push(this.text.join(' '));
	                  			}
	                  			if (this.isFinished) {
	                  				arrayIsFinished.push(this.isFinished);
	                  			}
	                  			if (this.logs) {
	                  				arrayLogs.push(this.logs);	
	                  			}
                  			}
                      			
                      	});

                      });

                      // update timing table
                      $('.start-time-js').text(timeConverter(startTime));
                      $('.end-time-js').text(timeConverter(endTime));
                      $('.elapsed-time-js').text(getTime(endTime, startTime));

                      // update step list
	                  $(stepList).each(function(i){
	                  	if (arrayIsFinished[i]) {
	                  		
		                  	$('.update-time-js', this).html(getTime(arraytimes[i][1], arraytimes[i][0]) + ' secs');
		                  	$('.s-text-js', this).html(arrayText[i]);
		                  	$('.s-logs-js a', this).text(arrayLogs[i][0][0]);
		                  	$('.s-logs-js a', this).attr('href', arrayLogs[i][0][1]);
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