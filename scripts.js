// Although this site is designed to function without JavaScript, this
// file provides extra features when JavaScript is enabled.

function toggleClass(elem, cls)
{
    var classes = elem.className.split(' ');
    var idx = classes.indexOf(cls);
    if (idx === -1 )
        classes.push(cls);
    else
        classes[idx] = '';
    elem.className = classes.join(' ');
}

// Full-screen toggle for Flash
var fstoggle = document.getElementById('fstoggle');
if (fstoggle)
{
    var headerbar = document.getElementById('headerbar');
    var flashvid  = document.getElementById('flashvid');
    var player    = document.getElementById('player');
    var html      = document.documentElement;
    var body      = document.body;
    var headerbarDisplay;
    var flashvidPosition;
    var flashvidWidth;
    var flashvidHeight;
    var playerMaxWidth;
    var bodyMarginTop;
    var htmlPaddingTop;

    fstoggle.onclick = function()
    {
        if (fstoggle.checked)
        {
            headerbarDisplay = headerbar.style.display;
            flashvidPosition = flashvid.style.position;
            flashvidWidth = flashvid.style.width;
            flashvidHeight = flashvid.style.height;
            playerMaxWidth = player.style.maxWidth;
            bodyMarginTop = body.style.marginTop;
            htmlMarginTop = html.style.marginTop;
            
            headerbar.style.display = 'none';
            flashvid.className = 'fullscreen';  // why doesn't this work?
            flashvid.style.position = 'absolute';
            flashvid.style.width = '100%';
            flashvid.style.height = '100%';
            player.style.maxWidth = '100%';
            body.style.marginTop = '0px';
            html.style.paddingTop = '0px';
            player.className = 'fullscreen';
        }
    }
}

// Collapsible drawers
var drawers = document.getElementsByClassName('drawer');
for (var i = 0; i < drawers.length; i++)
{
    drawers[i].onclick = function(e) { toggleClass(e.srcElement, 'collapsed'); };
}

// Resize iframes to fit their content
var iframes = document.getElementsByTagName('iframe');
for (var i = 0; i < iframes.length; i++)
{
    iframes[i].onload = 
        function(e)
        {
            var frameDocument = e.srcElement.contentWindow.document;
            var docHeight = frameDocument.documentElement.scrollHeight;
            var bodyHeight = frameDocument.body.scrollHeight;
            e.srcElement.style.height = Math.min(docHeight, bodyHeight) + 'px';
        }
}
