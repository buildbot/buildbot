define(['jquery'], function ($) {
	 "use strict";
    var realtime;
    
    realtime = {
        init: function () {
			// creating a new websocket
			//if ($('#tb-root').length != 0) {

				jQuery.fn.center = function() {
				var h = $(window).height();
			    var w = $(window).width();
			    var tu = this.outerHeight(); 
			    var tw = this.outerWidth(); 
			    
			    this.css("position", "absolute");

			    // adjust height to browser height

			    if (h < tu) {
			    	this.css("top", (h - tu + (tu - h) + 10) / 2 + $(window).scrollTop() + "px");
			    } else {
			    	this.css("top", (h - tu) / 2 + $(window).scrollTop() + "px");
			    }
				
				this.css("left", (w - tw) / 2 + $(window).scrollLeft() + "px");
				return this;
			};


				$('.popup-btn-js').each(function(i){
					$(this).attr('data-in', i)
				});

				$('.popup-btn-js').click(function(){
					var thisi = $(this).attr('data-in');
					var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
					$('body').append(preloader).show();
					$.ajax({
							url:'',
							cache: false,
							dataType: "html",
							data: {
								rt_update:'pending'
							},
							success: function(data) {
								$('#bowlG').remove();
								var doc = document.createElement('html');
			 					doc.innerHTML = data;
								
								var pendListRes = $('.more-info-box-js', doc);
								
								var mib;
								$(pendListRes).each(function(i){
									if (i == thisi) {
										mib = $(this);
									}
								});
								$(mib).appendTo('body').center().fadeIn('fast');
			
								$(window).resize(function() {
									$(mib).center();
								});

								$(document, '.close-btn').bind('click touchstart', function(e){
								if (!$(e.target).closest('.more-info-box-js').length || $(e.target).closest('.close-btn').length ) {
									$(mib).remove();
								}
					});
							}
					});
					
				});

				(function poll(){
					if ($('.current-job-js').length) {
						setTimeout(function() {
							$.ajax({
								url:'',
								cache: false,
								dataType: "html",
								complete: poll,
								timeout:2000, 
								success: function(data) {
									
									var doc = document.createElement('html');
				 					doc.innerHTML = data;
				 					
				 					var responseCurrent = $('.current-cont', doc);
				 					var responseStatus = $('.status-build-js', doc);
				 					var responseLastBuild = $('.last-build-js', doc);
				 					
				 					if ($('.current-job-js').length) {
					 					$('.current-cont').each(function(i){
					 						$(this).replaceWith($(responseCurrent)[i]);
					 					});
				 					} else {
				 						$('.status-build-js').each(function(i){
				 							$(this).replaceWith($(responseStatus)[i]);
				 						});
				 						$('.last-build-js').each(function(i){
				 							$(this).replaceWith($(responseLastBuild)[i]);
				 						});
				 					}	
								}
								
							});
						}, 2000);
					}
				})();

				(function( $ ) {
					 var sock = null;
			         var ellog = null;

			            var wsuri;
			            ellog = document.getElementById('log');

			            if (window.location.protocol === "file:") {
			               wsuri = "ws://localhost:9000";
			            } else {
			               wsuri = "ws://" + window.location.hostname + ":9000";
			            }

			            if ("WebSocket" in window) {
			               sock = new WebSocket(wsuri);
			            } else if ("MozWebSocket" in window) {
			               sock = new MozWebSocket(wsuri);
			            } else {
			               log("Browser does not support WebSocket!");
			               window.location = "http://autobahn.ws/unsupportedbrowser";
			            }

			            if (sock) {
			               sock.onopen = function() {
			                  log("Connected to " + wsuri);
			               }

			               sock.onclose = function(e) {
			                  log("Connection closed (wasClean = " + e.wasClean + ", code = " + e.code + ", reason = '" + e.reason + "')");
			                  sock = null;
			               }

			               sock.onmessage = function(e) {
			                  log(e.data);
			               }
			            }
			         
			         
			        function sumVal(arr) {
			          var sum = 0;
			          $.each(arr,function(){
			            sum+=parseFloat(this) || 0;
			          });
			          return sum;
			        };

			        
			         function broadcast(msg) {
			            console.log(msg + 'fd')
			            if (sock) {
			               sock.send(msg);
			               //log("Sent: " + msg);
			            } else {
			               //log("Not connected.");
			            }
			         };
					
			         function log(m) {

			            try {
			              console.log(m)
		                  var obj = JSON.parse(m);
		                  
		                  $.each(obj.builders, function (key, value) {
		                  	
		                  	if (value.state === 'offline') {
		                  		var offLine = true;
		                  		console.log(value.state)
		                  	}
	                      	//arrayPending.push(value.pendingBuilds);

	                      });

	                      if (offLine = true) {
	                      	broadcast('http://localhost:8001/json/slaves/lin-slave-02?as_text=1');		
	                      }
	                      
							/*

		                  var arrayPending = [];
		                    
	                      $.each(obj.builders, function (key, value) {

	                      	arrayPending.push(value.pendingBuilds);

	                      });
	                      
	                      $('#pendingBuilds').html(sumVal(arrayPending));

	                      var arraySlaves = [];
	                      
	                      $.each(obj.slaves, function (key) {
	                        arraySlaves.push(key);
	                      });

	                      $('#slavesNr').html(arraySlaves.length);
			               */
			            }
			            catch(err) {
			            }
			           
			         };
			     })( jQuery );
			 //}
		}
	};
	return realtime
});