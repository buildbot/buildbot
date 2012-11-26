/* utilities, and code related to direct access to the api
   deferred based!
*/
define(["dojo/_base/declare", "dojo/_base/Deferred", "dojo/_base/xhr"],
       function(declare, Deferred, xhr){
	   var api_url = dojo.baseUrl + "/../../../../api/";
	   return declare([], {
	       createAPIPath: function(a) {
		   var path=[];
		   for (var i = 0;i<a.length; i+=1) {
		       path.push(a[i]);
		   }
		   path = path.join("/");
		   console.log(path, a);
		   return path;
	       },
	       getApiV1: function() {
		   return xhr.get({handleAs:"json",url:api_url+"v1/"+this.createAPIPath(arguments)});
	       },
	       getApiV2: function() {
		   return xhr.get({handleAs:"json",url:api_url+"v2/"+this.createAPIPath(arguments)});
	       }
	   })(); // note the singleton..
       });
