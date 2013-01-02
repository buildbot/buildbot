define(["dojo/_base/declare", "dojo/_base/array","dojo/has","dojo/_base/html"],
function(declare, array, has){
    var updateHeightAndInherit = function () {
        this.updateHeight();
        return this.inherited(arguments);
    };

    return declare(null, {
        contentMaxHeight : 200,
        _willUpdateHeight : null,
        removeRow: function () {
            this.updateHeight();
            return this.inherited(arguments);
        },
        insertRow: function () {
            this.updateHeight();
            return this.inherited(arguments);
        },
        styleColumn: function () {
            this.updateHeight();
            return this.inherited(arguments);
        },
        updateHeight:function(){
            var self = this;

            if (has("ie") < 8 || has("quirks")) {
                /* ie non standard mode does not like this method */
                return;
            }
            if (self._willUpdateHeight === null) {
                self._willUpdateHeight = setTimeout(function(){
                    function heightFromChildrens(dom, max) {
                        var bounds = {bottom:-1,top:-1};
                        array.map(dom.childNodes, function(n){
                            var b = n.getBoundingClientRect();
                            if (b.bottom === 0) {return;}
                            if (bounds.top < 0 || b.top < bounds.top) {
                                bounds.top = b.top;
                            }
                            if (bounds.bottom < 0 || b.bottom > bounds.bottom) {
                                bounds.bottom = b.bottom;
                            }
                        });
                        var height = bounds.bottom - bounds.top;
                        if (max && height > max) {
                            self.contentNode.parentNode.style['overflow'] = "auto";
                            dom.style.height = max+"px";
                            self.updateHeight=function(){};
                        } else {
                            dom.style.height = height+"px";
                        }
                    }
                    self.contentNode.parentNode.style.overflow = "hidden";
                    heightFromChildrens(self.contentNode, self.contentMaxHeight);
                    heightFromChildrens(self.contentNode.parentNode);
                    heightFromChildrens(self.contentNode.parentNode.parentNode);
                    self.resize();
                    self._willUpdateHeight = null;
                }, 10);
            }
        }
    });
});
