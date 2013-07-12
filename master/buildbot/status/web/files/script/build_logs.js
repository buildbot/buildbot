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
	var bHeader = $('.build-log-header');

	$(bHeader).each(function(){
		var currHeight = $(this).height();
		var autoHeight = $(this).css('height', 'auto').height();

		$(this).height(currHeight)
		if (autoHeight <= currHeight) {
			$(this).next().hide();
		}
	});

	$('.js-header-btn').click(function(e){
		e.preventDefault();
		var theBtn = $(this);
		var pEl = $(this).prev();
		var curHeight = $(pEl).height();
		$(pEl).css('height', 'auto');
		var autoHeight = $(pEl).height();
		if ($(theBtn).hasClass('open')) {
			autoHeight = 70;
		}
		
		$(pEl).height(curHeight).animate({height:  autoHeight}, 700, function(){
			$(theBtn).toggleClass('open');
			if ($(theBtn).hasClass('open')) {
				$(theBtn).text('Hide header ');
			} else {
				$(theBtn).text('Show header ');
			}
		});
	});

	$('#expandAll').click(function(e){
		e.preventDefault();
		if ($(this).hasClass('open')) {
			$(this).text('Expand all ');
			
		} else {
			$(this).text('Collapse all ');

		};
		$('.js-header-btn').trigger('click');
		$(this).toggleClass('open');		
	});

});