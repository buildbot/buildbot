JAVASCRIPT = '''
// <;![Cdata[
//

//
// Functions used to display the build status bubble on box click.
//

// show the build status box. This is called when the user clicks on a block.
function showBuildBox(url, event) {
    //  Find the current curson position.
    var cursorPosTop = (window.event ? window.event.clientY : event.pageY)
    var cursorPosLeft = (window.event ? window.event.clientX : event.pageX)

    // Offset the position by 5, to make the window appears under the cursor.
    cursorPosTop  = cursorPosTop  + document.body.scrollTop -5 ;    
    cursorPosLeft = cursorPosLeft  + document.body.scrollLeft - 5;

    // Move the div (hidden) under the cursor.
    var divBox = document.getElementById('divBox');
    divBox.style.top = parseInt(cursorPosTop) + 'px';
    divBox.style.left = parseInt(cursorPosLeft) + 'px';

    // Reload the hidden frame with the build page we want to show.
    // The onload even on this frame will update the div and make it visible.
    document.getElementById("frameBox").src = url
    
    // We don't want to reload the page.
    return false;
}

// OnLoad handler for the iframe containing the build to show.
function updateDiv(event) { 
    // Get the frame innerHTML.
    var iframeContent = document.getElementById("frameBox").contentWindow.document.body.innerHTML;

    // If there is any content, update the div, and make it visible.
    if (iframeContent) {
        var divBox = document.getElementById('divBox'); 
        divBox.innerHTML = iframeContent ;
        divBox.style.display = "block";
    }
} 

// Util functions to know if an element is contained inside another element.
// We use this to know when we mouse out our build status div.
function containsDOM (container, containee) {
    var isParent = false;
    do {
        if ((isParent = container == containee))
            break;
        containee = containee.parentNode;
    } while (containee != null);

    return isParent;
}

// OnMouseOut handler. Returns true if the mouse moved out of the element.
// It is false if the mouse is still in the element, but in a blank part of it,
// like in an empty table cell.
function checkMouseLeave(element, event) {
  if (element.contains && event.toElement) {
    return !element.contains(event.toElement);
  }
  else if (event.relatedTarget) {
    return !containsDOM(element, event.relatedTarget);
  }
}

// ]]> 
'''
