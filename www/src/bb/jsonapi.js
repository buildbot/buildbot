/* utilities, and code related to direct access to the api
   deferred based!
*/
define(["dojo/_base/declare", "dojo/_base/Deferred", "dojo/request/xhr","dojo/json"],
       function(declare, Deferred, xhr, json){
	   var api_url = dojo.baseUrl + "/../../../../api/";
	   var jsonrpc_curid = 0;
	   return {
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
		   return xhr(api_url+"v1/"+this.createAPIPath(arguments),
			      {handleAs:"json"});
	       },
	       getApiV2: function() {
		   return xhr(api_url+"v2/"+this.createAPIPath(arguments),
			      {handleAs:"json"});
	       },
	       control: function(path, method, args) {
		   jsonrpc_curid+=1;
		   return xhr(api_url+"v2/"+this.createAPIPath(path),
			      {handleAs:"json",method:"POST",
			       headers: {
				   'Content-Type': 'application/json'
			       },
			       data:json.stringify({jsonrpc:"2.0",
				      method:method,
				      params:args,
				      id:jsonrpc_curid})
			      }
			     );
	       }
	   }; // note the singleton..
       });
