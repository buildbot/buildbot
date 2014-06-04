$(document).ready(function() {
	// class on selected menuitem
	$(function setCurrentItem(){
		var path = window.location.pathname.split("\/");
		
		 $('.top-menu a').each(function(index) {
		 	var thishref = this.href.split("\/");
	        if(thishref[thishref.length-1].trim().toLowerCase() == path[1].trim().toLowerCase())
	            $(this).parent().addClass("selected");
	    });
	});

	// split string on environment
	$('.build-log-header').each(function(){
		$(this).html($(this).text().replace("environment:", "<span class='env'></span>environment:"));

		var text = $('.env', this).parent().contents().filter(
	    function(){
	        return this.nodeType === 3 && this.nodeValue.trim() !== '';
	    }).last().wrapAll('<div class="all-text" />');

		if ($('.env', this).length === 0) {
			$(this).next($('.js-header-btn')).remove();		
		}
	});

	// toggle individual show hide button
	$('.js-header-btn').click(function(e){
		e.preventDefault();
		var theBtn = $(this);
		$(theBtn).prev('.build-log-header').children('.all-text').slideToggle('slow', function(){
			$(theBtn).toggleClass('open');
		});
	});

	// toggle the top expand button
	$('#toggleExpand').click(function(e){
		e.preventDefault();
		$(this).toggleClass('expanded');
		var text = $(this).hasClass('expanded')
		$(this).text(text == true ? 'Collapse all' : 'Expand all')
		if ($(this).hasClass('expanded')) {
			$('.js-header-btn').each(function(){
				if (!$(this).hasClass('open')) {
					$(this).trigger('click');		
				} 
			});		
		} else {
			$('.js-header-btn').each(function(){
				if ($(this).hasClass('open')) {
					$(this).trigger('click');		
				} 
			});		
		}
	});

});