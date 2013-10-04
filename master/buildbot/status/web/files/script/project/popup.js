define(['jquery', 'project/selectors'], function ($, selectors) {

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

			function popUpBtn(classBtn, classHide){

				$(classBtn).click(function(e){
					e.preventDefault();
					$('.cloned').remove();
					$('.command_forcebuild').removeClass('form-open');

					var clonedInfoBox = $(this).next().clone().addClass('cloned');

					$('body').append(clonedInfoBox);

					$(window).resize(function() {
						$(clonedInfoBox).center();
					});
					
					$(clonedInfoBox).center().fadeIn('fast', function (){
						$('.command_forcebuild', this).addClass('form-open')
						validateForm();
					});
				});
			};
			popUpBtn('.popup-btn-js');

			function closePopUp() {
					
				$(document, '.close-btn').bind('click touchstart', function(e){
					if (!$(e.target).closest('.more-info-box-js, .popup-btn-js, .more-info-box-js-2, .popup-btn-js-2').length || $(e.target).closest('.close-btn').length ) {
						$('.command_forcebuild').removeClass('form-open');
						$('.more-info-box-js, .more-info-box-js-2').hide();
						$('#content').empty();
						$('.cloned').remove();
					}
				}); 
				
			}
			closePopUp();

			// display popup box with external content	
			$('#getBtn').click(function() {

				$('.more-info-box-js, .more-info-box-js-2').hide();
				$('#content').empty();
				var path = $('#pathToCodeBases').attr('href');
				var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
				$('body').append(preloader).show();
				var mib3 = $('<div class="more-info-box more-info-box-js-2"><span class="close-btn"></span><h3>Codebases</h3><div id="content"></div></div>');
				$(mib3).appendTo('body');


				$.get(path)
				.done(function(data) {
					var $response=$(data);
					$('#bowlG').remove();
					
					var fw = $($response).find('#formWrapper')
					
					$(fw).appendTo($('#content'));
					
					$('#content .filter-table-input').remove();

					$(mib3).center().fadeIn('fast');
					
					$(window).resize(function() {
						$(mib3).center();
					});

					$("#formWrapper .select-tools-js").select2({
						width: selectors.getMaxChildWidth(".select-tools-js")
					});
					$("#formWrapper #commonBranch_select").select2({
						placeholder: "Common branches"
					});

					selectors.comboBox('#formWrapper .select-tools-js');
					
					$('.select2-drop').bind('click touchstart', function(e){
						e.stopPropagation();
						$(this).unbind(e);
					});	

		  			selectors.clickSort('#select2-drop .select2-results');
					$(window).resize(function() {
						$('.more-info-box-js-2').center();
					});
					
					$('#getForm').attr('action', window.location.href);	
					$('#getForm .grey-btn[type="submit"]').click(function(){
						$('.more-info-box-js-2').hide();				
					});

					$(document, '.close-btn').bind('click touchstart', function(e){
						if (!$(e.target).closest('.more-info-box-js-2').length || $(e.target).closest('.close-btn').length ) {
							$(mib3).remove();
						}
					});

				});
			});

			$('.ajaxbtn').click(function(e){
				e.preventDefault();
				var datab = $(this).attr('data-b');
				var dataindexb = $(this).attr('data-indexb');
				
				var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
				$('body').append(preloader).show();
				var mib3 = $('<div class="more-info-box more-info-box-js-3"><span class="close-btn"></span><h3>Run custom build</h3><div id="content1"></div></div>');
				$(mib3).appendTo('body');

				$.get('', {extform: true, datab: datab, dataindexb: dataindexb}).done(function(data) {

					$('#bowlG').remove();
					$(data).appendTo($('#content1'));
					$(mib3).center().fadeIn('fast');
					
					$(window).resize(function() {
						$(mib3).center();
					});

					$(document, '.close-btn').bind('click touchstart', function(e){
				
					    if (!$(e.target).closest(mib3).length || $(e.target).closest('.close-btn').length) {
					        	        	
					        $(mib3).remove();
					        	
					        $(this).unbind(e);
					    }
					});

				});

			});

		}
	}
	 return popup;
});