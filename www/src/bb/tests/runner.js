// This file is part of Buildbot.  Buildbot is free software: you can
// redistribute it and/or modify it under the terms of the GNU General Public
// License as published by the Free Software Foundation, version 2.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
// details.
//
// You should have received a copy of the GNU General Public License along with
// this program; if not, write to the Free Software Foundation, Inc., 51
// Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
//
// Copyright Buildbot Team Members

define(["dojo/main","doh/runner","doh/_browserRunner","dojo/hash","dojo/topic"],
       function(dojo, doh,br, hash, topic) {
	   var meths = ["showTestPage","showLogPage", "showPerfTestsPage"];
	   var old = {};
	   dojo.forEach(meths, function(m){
	       old[meths.indexOf(m)] = doh[m];
	       doh[m] = function() {
		   doh._switchtab(meths.indexOf(m));
	       };
	   });
	   doh._switchtab = function(i) {
	       var lis = dojo.query("#navtabs li");
	       dojo.forEach(lis, function(li){
		   li.className="";
	       });
	       lis[i].className = "active";
	       old[i]();
	   };
	   doh._updateGlobalProgressBar = function(p, success, group){
	       /* custom updateProgress for bootstrap */
	       var outerContainer = dojo.byId("progressOuter");
	       var gdiv = outerContainer.childNodes[doh._runedSuite - 1];
	       if(!gdiv){
		   gdiv = document.createElement('div');
		   outerContainer.appendChild(gdiv);
		   gdiv.className = 'bar bar-success';
		   gdiv.setAttribute('_target', group);
	       }
	       if(!success && !gdiv._failure){
		   gdiv._failure = true;
		   gdiv.className='bar bar-danger';
		   if(group){
		       gdiv.setAttribute('title', 'failed group ' + group);
		   }
	       }
	       var tp = parseInt(p * 10000,10) / 100;
	       gdiv.style.width = (tp - doh._currentGlobalProgressBarWidth) + "%";
	       return gdiv._failure;
	   };
	   function run_tests(teststr) {
	       require([teststr], function(test) {
		   doh.runOnLoad();
	       });
	   }
	   topic.subscribe("/dojo/hashchange", function(changedHash){
	       document.location.reload();
	   });
	   var test = hash();
	   if (! test) {
	       test  = "all";
	   }
	   run_tests("bb/tests/"+test);
       });
