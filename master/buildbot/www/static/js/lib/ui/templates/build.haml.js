define([],function(){function anonymous(locals){function _e(e){return(e+"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/\"/g,"&quot;")}with(locals||{})try{var _$output='<div class="container-fluid"><ul class="breadcrumb"><li><a href="#/builders">Builders</a></li><span class="divider">'+_e("/")+"</span><li>"+'<a href="'+_e("#/builders/"+b.builderName)+'">'+""+_e(b.builderName)+'</a></li><span class="divider">'+_e("/")+'</span><li class="active">'+'<a href="'+_e("#/builders/"+b.builderName+"/"+number)+'">'+"Build #"+_e(number)+'</a></li><div class="btn-group pull-right"><div class="btn"> <i alt="reason" class="icon-question-sign"></i> '+b.reason+'</div><div class="btn"> <i alt="buildslave" class="icon-hdd"></i> '+'<a href="'+_e("#/slaves/"+b.slave)+'">'+b.slave+"</a></div>"+function(){return isFinished()?'<div class="'+_e("btn "+btn_class(b.results))+'">'+""+_e(b.text.join(" "))+"</div>":""}.call(this)+'</div></ul><div style="margin-bottom:15px;margin-top:-15px" class="row-fluid"><div class="pull-right"><Strong>Actions:</Strong>'+function(){return isFinished()?' <button data-dojo-attach-point="onclick:doRebuild" class="btn btn-info">Promote</button> <button data-dojo-attach-point="onclick:doRebuild" class="btn btn-info">Rebuild</button>':""}.call(this)+'</div></div><div class="row-fluid"><div class="span5">'+function(){return isFinished()?"":'<div class="well"><h3>Build In Progress:</h3>'+function(){return b.when_time?"<p>ETA: "+_e(b.when_time)+" [ "+_e(when)+" ]</p>":""}.call(this)+' <li class="form-inline">'+_e(b.currentStep.name)+", "+_e(b.currentStep.text.join(" "))+' &nbsp;<div data-dojo-attach-point="stop_build_node" class="btn btn-inverse btn-mini pull-left">Stop Build</div></li> </div>'}.call(this)+'<div class="well"><h3>Steps and Logfiles:</h3><ol>'+function(){var e=[],t,n;for(t in b.steps)b.steps.hasOwnProperty(t)&&(n=b.steps[t],e.push('<li><div data-dojo-attach-event="onclick:toggleLogs" class="breadcrumb step-sts">'+_e(n.name)+function(){return n.isFinished?'<div class="'+_e("btn pull-right "+btn_class(n.results[0]))+'">'+""+_e(n.text.join(" "))+"</div>":""}.call(this)+"</div>"+'<ol style="'+_e(stepLogsDisplayStyle(n))+'">'+function(){return n.logs.length===0?"<div>- no logs -</div>":""}.call(this)+function(){var e=[],t,r;for(t in n.logs)n.logs.hasOwnProperty(t)&&(r=n.logs[t],e.push('<li><a href="'+_e(r[1])+'">'+""+_e(r[0])+"</a></li>"));return e.join("")}.call(this)+function(){var e=[],t,r;for(t in n.urls)n.urls.hasOwnProperty(t)&&(r=n.urls[t],e.push('<li><a href="'+_e(r[1])+'">'+""+_e(r[0])+"</a></li>"));return e.join("")}.call(this)+"</ol></li>"));return e.join("")}.call(this)+'</ol></div></div><div class="span1"></div><div class="span6 well"><h3>build properties</h3><div data-dojo-attach-point="propertiesgrid_node" class="div"></div></div></div></div>';return _$output}catch(e){return"\n<pre class='error'>"+_e(e.stack)+"</pre>\n"}}return anonymous})