define(['jquery', 'helpers'], function ($, helpers) {

    "use strict";
    var popup;

	popup = {
		init: function () {
		// center infobox
		
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

			// validate the forcebuildform
			function validateForm() {
				var formEl = $('.form-open');
				var excludeFields = ':button, :hidden, :checkbox, :submit';
				$('.grey-btn', formEl).click(function(e) {

					var allInputs = $('input', formEl).not(excludeFields);
					
					var rev = allInputs.filter(function() {
						return this.name.indexOf("revision") >= 0;
					});
					
					var emptyRev = rev.filter(function() {
						return this.value === "";
					});

					if (emptyRev.length > 0 && emptyRev.length < rev.length) {
						
						rev.each(function(){
		    				if ($(this).val() === "") {
								$(this).addClass('not-valid');
							} else {
								$(this).removeClass('not-valid');
							}
		    			});

		    			$('.form-message', formEl).hide();

		    			if (!$('.error-input', formEl).length) {
		    				$(formEl).prepend('<div class="error-input">Fill out the empty revision fields or clear all before submitting</div>');
		    			} 
						e.preventDefault();
					}
				});
				
			}

			//For non ajax boxes
			$('.popup-btn-js-2').click(function(e){
				e.preventDefault();

				var clonedInfoBox = $(this).next('.more-info-box-js').clone();
				
				$(clonedInfoBox).appendTo('body').center().fadeIn('fast', function() {
					$(document, '.close-btn').bind('click touchstart', function(e){
						if (!$(e.target).closest('.more-info-box-js').length || $(e.target).closest('.close-btn').length ) {
							$(clonedInfoBox).remove();
						}
					});	
				});
				$(window).resize(function() {
					$(clonedInfoBox).center();
				});
			});


			//For builders pending box
			$('.popup-btn-js').each(function(i){
				$(this).attr('data-in', i)
			});
			
			$('.popup-btn-js').click(function(e){
				e.preventDefault();
				var thisi = $(this).attr('data-in');
				var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
				var rtUpdate = $(this).attr('data-rt_update');

				$('body').append(preloader).show();
				// get currentpage with url parameters
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

			// display popup box with external content	
			$('#getBtn').click(function() {

				$('.more-info-box-js').hide();
				$('#content').empty();
				var path = $('#pathToCodeBases').attr('href');
				var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
				$('body').append(preloader).show();
				var mib = $('<div class="more-info-box more-info-box-js"><span class="close-btn"></span><h3>Codebases</h3><div id="content"></div></div>');
				$(mib).appendTo('body');


				$.get(path)
				.done(function(data) {
					
					$('#bowlG').remove();
					
					var fw = $(data).find('#formWrapper')
					
					$(fw).appendTo($('#content'));
					
					$('#content .blue-btn').val('update');

					// remove unwanted html for the poopup box
					$('#content .filter-table-input label, #content .filter-table-input .help-txt').remove();

					$(mib).center().fadeIn('fast');
					
					$(window).resize(function() {
						$(mib).center();
					});


					require(['selectors'],function(selectors) {
			        	selectors.comboBox('#formWrapper .select-tools-js');
			        	selectors.init();
						$(window).resize(function() {
							$('.more-info-box-js').center();
						});
					});
					
					$('#getForm').attr('action', window.location.href);	
					$('#getForm .blue-btn[type="submit"]').click(function(){
						$('.more-info-box-js').hide();				
					});

					$(document, '.close-btn').bind('click touchstart', function(e){
						if (!$(e.target).closest('.more-info-box-js').length || $(e.target).closest('.close-btn').length ) {
							$(mib).remove();
						}
					});

				});
			});

			// html for 
			function htmlModule (htmlChunk) {

				if (htmlChunk == 'isForm') {
					var mib3 = 
					$('<div class="more-info-box remove-js">' +
					'<span class="close-btn"></span>' +
					'<h3>Run custom build</h3>' +
					'<div id="content1"></div></div>');
					
				} else {
					var mib3 =
					$('<div class="more-info-box remove-js">' + 
					'<span class="close-btn"></span>' + 
					'<h3>Buildslaves</h3>' + 
					'<div id="content1"></div></div>');			
				}
				return mib3;
			}

			// tab list for custom build
			function customTabs (){
				$('.tabs-list li').click(function(i){
					var indexLi = $(this).index();
					$(this).parent().find('li').removeClass('selected');
					$(this).addClass('selected');
					$('.content-blocks > div').each(function(i){
						if ($(this).index() != indexLi) {
							$(this).hide();
						} else {
							$(this).show();
						}
					});

				});
			}
			
			// custom buildpopup on builder and builders
			$('.ajaxbtn').click(function(e){
				e.preventDefault();
				var datab = $(this).attr('data-b');
				var dataindexb = $(this).attr('data-indexb');
				var rtUpdate = $(this).attr('data-rt_update');
				var htmlChunk = $(this).attr('data-htmlchunk'); 
				var preloader = $('<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>');
				$('body').append(preloader).show();
				var mib3 = htmlModule (htmlChunk);
				mib3.appendTo($('body'));
				
				// get currentpage with url parameters
				$.get('', {rt_update: rtUpdate, datab: datab, dataindexb: dataindexb}).done(function(data) {
					var formContainer = $('#content1');
					preloader.remove();
					$(data).appendTo(formContainer);

					
					// Insert full name from cookie
					
					$("#usernameDisabled, #usernameHidden", formContainer)
					.val(helpers.getCookie("firstName") + ' ' + helpers.getCookie("lastName"));
					

					mib3.center().fadeIn('fast');
					
					$(window).resize(function() {
						mib3.center();
					});
					// customTabs();
					$(document, '.close-btn').bind('click touchstart', function(e){
				
					    if (!$(e.target).closest(mib3).length || $(e.target).closest('.close-btn').length) {
					        	        	
					        mib3.remove();
					        	
					        $(this).unbind(e);
					    }
					});

				});

			});
		
		}
	}
	 return popup;
});