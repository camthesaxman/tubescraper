#!/usr/bin/env python3
#
# YouTube simplifier
#

import datetime
import html
import http.server
import json
import re
import requests
import socketserver
import subprocess
import sys
import urllib
import yt_dlp

class Error404(Exception):
    pass

class Error500(Exception):
    pass

# This bar appears at the top of every page
headerBar = '''
<div id="headerbar">
    <a id="homelink" href="/"><img id="homelinkicon" src="/tubescraper_logo_64.png" alt="Home">Tube Scraper</a>
    <form id="searchform" action="/results" method="get">
        <input id="query" type="text" name="search_query" value="%s" placeholder="Search">
        <input id="searchicon" type="image" src="/search_icon.png" alt="Search">
    </form>
</div>
'''

def serve_page(handler, status, content):
    handler.send_response(status)
    handler.send_header('Content-type', 'text/html')
    handler.end_headers()
    handler.wfile.write(content)

# Constructs a page with the specified title and content
def make_page(title, content, params=None, includeHeaderBar=True):
    # If a search param is given, auto-populate the search field with it.
    if params == None:
        searchParam = ''
    else:
        searchParam = esc(params['search_query'][0])
    # html begin
    page = '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">'
    page += '<html>\n'
    # head
    page += '<head>\n'
    page += '  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
    page += '  <meta name="viewport" content="user-scalable=0, width=device-width">\n'
    page += '  <link rel="icon" href="/favicon.ico">'
    page += '  <title>%s - TubeScraper</title>\n' % esc(title)
    page += '  <link rel="stylesheet" href="/style.css">\n'
    page += '  <!--[if lt IE 7]><link rel="stylesheet" href="/ie6.css"><![endif]-->\n'
    page += '</head>\n'
    # body
    if includeHeaderBar:
        page += '<body>\n' + headerBar % searchParam
    else:
        page += '<body style="margin: 0px">\n'  # get rid of header bar space
    page += '<div id="content">\n' + content + '</div>'
    page += '</body>'
    # scripts
    page += '<script type="text/javascript" src="/scripts.js"></script>'
    # html end
    page += '</html>'
    return page.encode(encoding='utf-8')

# Decodes backslash escape sequences in strings
def unescape_string(string):
    output = []
    it = iter(string)
    for c in it:
        if c == '\\':
            c = next(it)
            if c == '\\':
                output.append('\\')
            elif c == '/':
                output.append('/')
            elif c == 'x':
                n1 = next(it)
                n2 = next(it)
                n = ''.join([n1, n2])
                output.append(chr(int(n,16)))
            else:
                raise Exception('unhandled ' + c)
        else:
            output.append(c)
    return ''.join(output)

# like html.escape, but doesn't throw an exception when None is passed in
def esc(string):
    return None if string == None else html.escape(string)

def remove_yt_domain(url):
    return url[url.find('youtube.com')+len('youtube.com'):]

# Converts number of seconds to H:M:S string
def secs_to_hms(time):
    if time == None:
        return None
    s = time % 60
    time //= 60
    m = time % 60
    time //= 60
    h = time
    if h >= 1:
        return '%i:%02i:%02i' % (h, m, s)
    else:
        return '%i:%02i' % (m, s)

# converts a number to a suffixed (K, M, or B) version
def suffix_number(n):
    if n == None:
        return 'unknown'
    if n >= 1000000000:
        fmt = '%gB'
        n /= 1000000000
    elif n >= 1000000:
        fmt = '%gM'
        n /= 1000000
    elif n >= 1000:
        fmt = '%gK'
        n /= 1000
    else:
        return str(n)
    if n >= 100:
       n = int(n)
    n = n * 100 // 10 / 10
    return fmt % n

def smallest_thumbnail(thumbs):
    ret = None
    for thumb in thumbs:
        if ret == None or thumb['width'] * thumb['height'] < ret['width'] * ret['height']:
            ret = thumb
    return ret

# retrieves either the text runs or simpleText, whichever is present
def get_text(obj):
    if obj == None:
        return ''
    if 'simpleText' in obj:
        return obj['simpleText']
    if 'runs' in obj:
        text = ''
        for run in obj['runs']:
            text += run['text']
        return text
    return ''

# Extracts the ytInitialData JSON from the page and returns it as a string
def extract_yt_initial_data(input):
    match = re.search(r"ytInitialData = '([^']*)'", input)
    if match != None:
        return unescape_string(match.group(1))
    # Try it without the quote (some channels have it in this form)
    match = re.search(r"ytInitialData = ({.*?});</script>", input)
    if match != None:  # not found
        return match.group(1)
    raise Error500

def nav_buttons(text, prevUrl, nextUrl):
    content = '<div>'
    if prevUrl:
        content += '<a class="navbutton" href="%s">&lt; Prev</a> ' % esc(prevUrl)
    content += esc(text)
    if nextUrl:
        content += ' <a class="navbutton" href="%s">Next &gt;</a>' % esc(nextUrl)
    content += '</div>'
    return content

# A channel, video, or playlist item within a list
# Consists of a link containing the thumbnail
# and another div containing text
def make_item(title, url, thumbnailUrl=None, thumbnailText=None, channel=None, channelUrl=None, otherText=None):
    content = '<div class="item item-video">\n'
    content += ' <a class="thumbnail" href="%s" target="_top">' % esc(url)
    if thumbnailUrl:
        content += '<img src="%s" alt="Thumbnail">' % esc(thumbnailUrl)
    if thumbnailText:
        content += '<div class="thumbnail-overlay">%s</div>' % esc(thumbnailText)
    content += '</a>'
    content += ' <div class="details">'
    line1 = '<a class="item-title" href="%s" target="_top">%s</a>' % (esc(url), esc(title))
    line2 = esc(otherText) if otherText else None
    line3 = '<a href="%s" target="_top">%s</a>\n' % (esc(channelUrl), esc(channel)) if channel else None
    content += '<br>'.join(filter(None, [line1, line2, line3]))
    content += ' </div>\n'
    content += '</div>\n'
    return content

def render_video_item(title, url, thumbUrl, viewsText, duration=None, date=None, channel=None, channelUrl=None):
    return make_item(
        title         = title,
        url           = url,
        thumbnailUrl  = thumbUrl,
        thumbnailText = duration,
        channel       = channel,
        channelUrl    = channelUrl,
        otherText     = ' - '.join(filter(None, [viewsText, date]))
    )

def render_videoRenderer(vid):
    title = get_text(vid['title'] if 'title' in vid else vid['headline'])
    try:
        channelUrl = vid['shortBylineText']['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']
    except KeyError:
        channelUrl = None
    return render_video_item(
        title      = title,
        url        = vid['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'],
        thumbUrl   = smallest_thumbnail(vid['thumbnail']['thumbnails'])['url'],
        duration   = get_text(vid.get('lengthText')),
        viewsText  = get_text(vid.get('shortViewCountText')),
        date       = get_text(vid.get('publishedTimeText')),
        channel    = get_text(vid['shortBylineText']),
        channelUrl = channelUrl)

def render_reelItemRenderer(item):
    return render_video_item(
        title     = get_text(item['headline']),
        url       = item['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'],
        thumbUrl  = smallest_thumbnail(item['thumbnail']['thumbnails'])['url'],
        viewsText = get_text(item['viewCountText'])
    )

def render_channelRenderer(chan):
    thumbUrl = smallest_thumbnail(chan['thumbnail']['thumbnails'])['url']
    if thumbUrl.startswith('//'):
        thumbUrl = 'https:' + thumbUrl
    subscriberCountText = get_text(chan['videoCountText']) if 'videoCountText' in chan else None
    return make_item(
        title        = get_text(chan['title']),
        url          = chan['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'],
        thumbnailUrl = thumbUrl,
        otherText    = subscriberCountText
    )

def render_playlist_item(title='???', url='', thumbUrl='', vidCountText='', channel='', channelUrl=''):
    return make_item(
        title        = title,
        url          = url,
        thumbnailUrl = thumbUrl,
        channel      = channel,
        channelUrl   = channelUrl,
        otherText    = 'Playlist - ' + vidCountText
    )

def render_compactPlaylistRenderer(playlist):
    if 'runs' in playlist['longBylineText']:
        channelUrl = playlist['longBylineText']['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url']
    else:
        channelUrl = ''
    return render_playlist_item(
        title        = get_text(playlist['title']),
        url          = playlist['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'],
        thumbUrl     = smallest_thumbnail(playlist['thumbnail']['thumbnails'])['url'],
        vidCountText = get_text(playlist['videoCountText']),
        channel      = get_text(playlist['longBylineText']),
        channelUrl   = channelUrl)

def render_playlistRenderer(playlist):
    return render_playlist_item(
        title        = get_text(playlist['title']),
        url          = playlist['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'],
        thumbUrl     = smallest_thumbnail(playlist['thumbnails'][0]['thumbnails'])['url'],
        vidCountText = get_text(playlist['videoCountText']),
        channel      = playlist['longBylineText']['runs'][0]['text'],
        channelUrl   = playlist['longBylineText']['runs'][0]['navigationEndpoint']['commandMetadata']['webCommandMetadata']['url'])

# Renders a contents node
def render_contents(contents):
    content = ''
    for thing in contents:
        if type(contents) is dict:  # iterating over keys of a dict
            kind = thing
            obj = contents[thing]
        elif type(contents) is list:  # iterating over list of dicts, with each of the form { kind : {obj} }
            kind = list(thing)[0]
            obj = thing[kind]
        # List renderers
        if kind == 'sectionListRenderer':
            content += render_contents(obj['contents'])
        elif kind == 'verticalListRenderer':
            content += render_contents(obj['items'])
        # Item renderers
        elif kind == 'videoRenderer':
            content += render_videoRenderer(obj)
        elif kind == 'playlistRenderer':
            content += render_playlistRenderer(obj)
        elif kind == 'radioRenderer':
            content += render_compactPlaylistRenderer(obj)
        elif kind == 'channelRenderer':
            content += render_channelRenderer(obj)
        #
        elif kind == 'twoColumnSearchResultsRenderer':
            content += render_contents(obj['primaryContents'])
        elif kind == 'itemSectionRenderer':
            content += render_contents(obj['contents'])
        elif kind in ('singleColumnBrowseResultsRenderer', 'twoColumnBrowseResultsRenderer'):
            content += render_contents(obj['tabs'])
        elif kind == 'tabRenderer':
            if 'title' in obj:
                content += '<div class="item"><h2>%s</h2></div>' % esc(obj['title'])
            content += render_contents(obj['content'])
        elif kind == 'richGridRenderer':
            content += render_contents(obj['contents'])
        elif kind == 'richItemRenderer':
            content += render_contents(obj['content'])
        elif kind == 'videoWithContextRenderer':
            content += render_videoRenderer(obj)
        elif kind == 'richSectionRenderer':
            content += render_contents(obj['content'])
        # Shelf renderers
        elif kind == 'shelfRenderer':
            content += '<div class="drawer">%s%s</div>' % (esc(get_text(obj['title'])), render_contents(obj['content']))
        elif kind == 'brandVideoShelfRenderer':
            content += '<div class="drawer">%s<p>%s</p>%s</div>' % (
                esc(get_text(obj['title'])),
                esc(get_text(obj['subtitle'])),
                render_contents(obj['content']))
        elif kind == 'reelShelfRenderer':
            content += '<div class="drawer">%s<div class="reel-container">%s</div></div>' % (esc(get_text(obj['title'])), render_contents(obj['items']))
        elif kind == 'richShelfRenderer':
            content += '<div class="drawer">%s<div class="reel-container">%s</div></div>' % (esc(get_text(obj['title'])), render_contents(obj['contents']))
        #
        elif kind == 'reelItemRenderer':
            content += render_reelItemRenderer(obj)
        elif kind == 'showingResultsForRenderer':
            content += '<div class="item">Showing results for <a href="%s" style="font-style:italic">%s</a>. Search instead for <a href="%s" style="font-style:italic">%s</a>?</div>' % (
                esc(obj['correctedQueryEndpoint']['commandMetadata']['webCommandMetadata']['url']),
                esc(get_text(obj['correctedQuery'])),
                esc(obj['originalQueryEndpoint']['commandMetadata']['webCommandMetadata']['url']),
                esc(get_text(obj['originalQuery'])))
        elif kind == 'didYouMeanRenderer':
            content += '<div class="item">Did you mean <a href="%s" style="font-style:italic">%s</a>?</div>' % (
                esc(obj['correctedQueryEndpoint']['commandMetadata']['webCommandMetadata']['url']),
                esc(get_text(obj['correctedQuery'])))
        elif kind == 'backgroundPromoRenderer':
            content += '<div class="item"><b>%s</b><p>%s</p></div>' % (
                esc(get_text(obj['title'])),
                esc(get_text(obj['bodyText'])))
        else:
            print('TODO: ' + kind)
            #content += '<div class="item" style="font-family:monospace">Unknown renderer: %s</div>' % kind
    return content

##### Channel Page #####

def get_playlist_info(url, minItem=None, maxItem=None):
    opts = {'extract_flat':True}
    if minItem != None and maxItem != None:
        opts['playlist_items'] = '%i-%i' % (minItem, maxItem)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if info == None:
        raise Error404
    return info

def make_channel_page(info, path, pageNum):
    title = info['channel']
    # get banner and avatar
    banner = None
    avatar = None
    for t in info['thumbnails']:
        if 'width' in t and 'height' in t:
            if t['width'] == t['height']:
                if avatar == None:
                    avatar = t
            else:
                if banner == None:
                    banner = t
    # banner
    content = ''
    if banner:
        content += '<img src="%s" style="width:100%%" alt="Channel Banner">' % esc(banner['url'])
    # channel header
    content += '<div class="channel-header">'
    if avatar:
        content += '<img class="thumbnail" src="%s" style="width:100px" alt="Channel Avatar">' % esc(avatar['url'])
    content += '<h1>%s</h1>%s subscribers' % (esc(info['channel']), suffix_number(info['channel_follower_count']) )
    content += '</div>'
    # description
    content += '<div class="drawer">Channel Description<p class="description">%s</p></div>' % esc(info['description'])
    # videos
    if info['entries'][0]['_type'] == 'playlist':  # has multiple tabs
        for e in info['entries']:
            url = remove_yt_domain(e['webpage_url'])
            content += '<div class="drawer">%s' % esc(e['title'])
            content += '<iframe src="%s" style="height:%ipx">Loading...</iframe>' % (esc(url), 121*10+25)
            content += '</div>'
    else:  # has only a single tab
        content += '<div class="drawer">Videos'
        content += '<iframe name="videos" src="%s/videos" style="height:1230px">Loading...</iframe>' % esc(path)
        content += '</div>'
    # playlists
    content += '<div class="drawer">Playlists'
    content += '<iframe name="playlists" src="%s/playlists" style="height:1230px">Loading...</iframe>' % esc(path)
    content += '</div>'
    return make_page(title, content)

def make_channel_video_list(path, pageNum):
    # 10 videos per page
    min = (pageNum - 1) * 10 + 1
    max = min + 9
    # get an extra one so we can tell if it's the last page
    info = get_playlist_info('https://www.youtube.com' + path, min, max + 1)
    if len(info['entries']) <= 10:
        max = min + len(info['entries']) - 1
    if info == None:
        return Error404('Failed to get playlist info from YouTube.')
    entries = info['entries'][:10]
    if pageNum == 1 and len(entries) == 0:
        content = '<p>No videos</p>'
    else:
        sep = '&' if '?' in path else '?'
        prevUrl = '%s%spage=%i' % (path, sep, pageNum - 1) if pageNum > 1 else None
        nextUrl = '%s%spage=%i' % (path, sep, pageNum + 1) if len(info['entries']) > 10 else None
        content = nav_buttons('Showing items %i to %i' % (min, max), prevUrl, nextUrl)
        if path.split('/')[-1] == 'playlists':
            # playlists
            for p in entries:
                content += render_playlist_item(
                    title = p['title'],
                    url = '/playlist?list=' + p['id'],
                    channel = info['channel'],
                    channelUrl = remove_yt_domain(info['channel_url']))
        else:
            # videos
            for v in entries:
                thumb = smallest_thumbnail(v['thumbnails'])
                content += render_video_item(
                    title      = v['title'],
                    url        = remove_yt_domain(v['url']),
                    thumbUrl   = thumb['url'].split('?')[0],  # Remove params. They cause the thumbnail to not show up on Webkit for some reason
                    duration   = secs_to_hms(v['duration']),
                    viewsText  = suffix_number(v['view_count']) + ' views',
                    date       = v['release_timestamp'],
                    channel    = info['channel'],
                    channelUrl = remove_yt_domain(info['channel_url']))
    return make_page('Videos', content, includeHeaderBar=False)

def make_playlist_video_list(path, plist, pageNum):
    info = get_playlist_info('https://www.youtube.com' + path)
    if info == None:
        raise Error404('Failed to get playlist info from YouTube.')
    content = '<h1>%s</h1>%i videos' % (esc(info['title']), len(info['entries']))
    for v in info['entries']:
        thumb = smallest_thumbnail(v['thumbnails'])
        content += render_video_item(
            title      = v['title'],
            url        = remove_yt_domain(v['url']) + ('&list=%s' % plist),
            thumbUrl   = thumb['url'].split('?')[0],  # Remove params. They cause the thumbnail to not show up on Webkit for some reason
            duration   = secs_to_hms(v['duration']),
            viewsText  = suffix_number(v['view_count']) + ' views',
            date       = v['release_timestamp'],
            channel    = info['channel'],
            channelUrl = remove_yt_domain(info['channel_url']))
    return make_page(info['title'], content)

def serve_channel_page(handler, path, params):
    if 'page' in params:
        pageNum = int(params['page'][0])
    else:
        pageNum = 1
    if pageNum < 1:
        pageNum = 1

    parts = path.split('/')
    subdir = None
    if len(parts) < 2:
        raise Error404

    rest = []
    if parts[1] == 'channel':
        if len(parts) not in (3, 4):
            raise Error404
        rest = parts[3:]
    elif parts[1].startswith('@'):
        if len(parts) not in (2, 3):
            raise Error404
        rest = parts[2:]

    if len(rest) == 1:
        # Serve a subpage
        serve_page(handler, 200, make_channel_video_list(path, pageNum))
    else:
        # Serve the channel page
        url = 'https://m.youtube.com' + path + '?app=m'
        info = get_playlist_info(url, 1, 10)
        if info == None:
            raise Error404
        serve_page(handler, 200, make_channel_page(info, path, pageNum))

##### Playlist Page #####

def serve_playlist_page(handler, params):
    if 'list' not in params:
        raise Error404('missing list param')
    if 'page' in params:
        pageNum = int(params['page'][0])
    else:
        pageNum = 1
    if pageNum < 1:
        pageNum = 1
    plist = params['list'][0]
    serve_page(handler, 200, make_playlist_video_list('/playlist?list=%s' % plist, plist, pageNum))
    return

##### Home Page #####

def serve_main_page(handler):
    # fetch results from YouTube
    r = requests.get('https://www.youtube.com')
    if r.status_code == 200:
        data = extract_yt_initial_data(r.text)
        #print(data)
        resultsJSON = json.loads(data)
        content = render_contents(resultsJSON['contents'])
        serve_page(
            handler,
            200,
            make_page('Home', content))
    elif r.status_code == 404:
        raise Error404
    else:
        raise Error500
    return

##### Results Page #####

def make_results_page(params, input):
    rawParam = urllib.parse.unquote(params['search_query'][0])
    content = '<p><b>Search results for "%s"</b></p>' % esc(rawParam)
    data = extract_yt_initial_data(input)
    if data == None:
        content += '<p>No results found</p>'
    else:
        # JSON
        #print(data)
        resultsJSON = json.loads(data)
        content += '<p>Estimated %s results</p>' % esc(resultsJSON['estimatedResults'])
        contents = resultsJSON['contents']
        content += render_contents(resultsJSON['contents'])
        return make_page(rawParam, content, params=params)

def serve_results_page(handler, params, query):
    # fetch results from YouTube
    r = requests.get('https://www.youtube.com/results?' + query)
    if r.status_code == 200:
        serve_page(handler, 200, make_results_page(params, r.text))
    elif r.status_code == 404:
        raise Error404
    else:
        exit()
    return

##### Watch Page #####

videoHTML = '''
<video id="player" controls poster="%s">
  <source type="video/mp4" src="%s"></source>%s
  <!-- Flash fallback -->
  <embed id="flashvid" type="application/x-shockwave-flash" src="/player_flv_maxi.swf" width="540" height="360" wmode="transparent" FlashVars="%s"></embed>
  <label><input id="fstoggle" type="checkbox">Full Screen</label>
</video>
'''

videoInfoHTML = '''
<div class="videoinfo">
  <h1>%s</h1>
  <p>%s views - Uploaded on %s</p>
  <a href="%s">%s</a>
</div>
'''

def print_format_info(formats):
    print("ID         A.Codec         V.Codec          Width Height  FPS Ext   Note")
    for fmt in formats:
        w = fmt.get('width', 0)
        h = fmt.get('height', 0)
        fps = fmt.get('fps', 0)
        w = w if w != None else 0
        h = h if h != None else 0
        fps = fps if fps != None else 0
        print('%-10s %-15s %-15s %6i %6i %4i %-5s %s' % (fmt['format_id'], fmt['acodec'], fmt['vcodec'], w, h, fps, fmt['ext'], fmt.get('format_note')))

def serve_watch_page(handler, videoId, plist=None):
    try:
        with yt_dlp.YoutubeDL() as ydl:
            url = 'https://m.youtube.com/watch?app=m&v=' + videoId
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError:
        raise Error404
    # Get captions
    captionsHTML = ''
    for st in info['subtitles']:
        formats = info['subtitles'][st]
        for fmt in formats:
            if fmt['ext'] == 'vtt':
                url = remove_yt_domain(fmt['url'])
                lang = fmt['name']
                captionsHTML += '\n  <track label="%s" kind="subtitles" srclang="%s" src="%s"></track>' % (esc(lang), esc(st), esc(url))
    for st in info['automatic_captions']:
        if st.startswith('en'):
            formats = info['automatic_captions'][st]
            for fmt in formats:
                if fmt['ext'] == 'vtt':
                    url = remove_yt_domain(fmt['url'])
                    lang = fmt['name'] + ' (auto-generated)'
                    captionsHTML += '\n  <track label="%s" kind="subtitles" srclang="%s" src="%s"></track>' % (esc(lang), esc(st), esc(url))
    # Get video formats
    print_format_info(info['formats'])
    formats = {fmt['format_id']:fmt for fmt in info['formats']}
    uploadDate = datetime.datetime.strptime(info['upload_date'], '%Y%m%d')
    fmt = formats['18']
    # video
    flashUrl = '/flvconvert.flv?src=' + fmt['url']
    flashVars = esc('margin=0&showstop=1&showiconplay=1&showtime=1&flv=%s' % urllib.parse.quote(flashUrl))
    content = videoHTML % (esc(info['thumbnail']), esc(fmt['url']), captionsHTML, flashVars)
    # info
    content += videoInfoHTML % (
        esc(info['title']),
        format(info['view_count'], ',d'),
        uploadDate.strftime('%d %B %Y'),
        esc(remove_yt_domain(info['channel_url'])),
        esc(info['uploader']))
    # playlist
    if plist:
        info = get_playlist_info('https://www.youtube.com/playlist?list=%s' % plist)
        if info:
            videos = info['entries']
            prevUrl = nextUrl = None
            index = None
            for i in range(0, len(videos)):
                v = videos[i]
                if v['id'] == videoId:
                    index = i
            for i in range(0, len(videos)):
                if index - 1 == i:
                    prevUrl = remove_yt_domain(videos[i]['url']) + '&list=' + plist
                elif index + 1 == i:
                    nextUrl = remove_yt_domain(videos[i]['url']) + '&list=' + plist
            content += '<div class="drawer">Playlist\n'
            content += nav_buttons('%i / %i' % (index + 1, len(videos)), prevUrl, nextUrl)
            # videos
            content += '  <ol class="watch-playlist">\n'
            for v in info['entries']:
                url = remove_yt_domain(v['url']) + '&list=' + plist
                content += '    <li%s><a href="%s">%s</a></li>\n' % (
                    ' class="selected"' if v['id'] == videoId else '',
                    esc(url),
                    esc(v['title']))
            content += '  </ol>\n'
            content += '</div>\n'
    # description
    content += '<div class="drawer">Description<p class="description">%s</p></div>' % info['description']
    # comments
    content += '<div class="drawer">Comments<iframe src="/comments?v=%s"></div>\n' % videoId
    serve_page(handler, 200, make_page(info['title'], content))

##### Comments Page #####

commentHTML = '''
<div class="comment">
 <a href="/channel/%s" target="_top"><img src="%s"></a>
 <div class="comment-info">
  %s - %s
  <p>%s</p>
  %s
 </div>
  %s
</div>
'''

def render_comment(comment):
    repliesHTML = ''.join([render_comment(c) for c in comment['replies']]) if 'replies' in comment else ''
    return commentHTML % (
        esc(comment['author_id']),
        esc(comment['author_thumbnail']),
        esc(comment['author']),
        esc(comment['time_text']),
        esc(comment['text']),
        '%i Like%s' % (comment['like_count'], '' if comment['like_count'] == 1 else 's'),
        repliesHTML)
    return content

def serve_comments_page(handler, params):
    videoId = params['v'][0]
    url = 'https://youtube.com/watch?v=' + videoId
    opts = {'getcomments':True, 'extract_flat':True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    # get root comments
    rootComments = [c for c in info['comments'] if c['parent'] == 'root']
    # get replies
    for comment in rootComments:
        comment['replies'] = [c for c in info['comments'] if c['parent'] == comment['id']]
    content = ''.join([render_comment(c) for c in rootComments])
    serve_page(handler, 200, make_page('Comments', content, includeHeaderBar=False))

##### Flash Converter #####

def serve_flv(handler, url):
    # get duration
    cmd = ['ffprobe', url]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise Error404
    m = re.search(r'Duration: ([^,]*),', str(result.stderr))
    if m == None:
        raise Error500
    duration = m.group(1)
    cmd = ['ffmpeg', '-hide_banner', '-nostats', '-i', url, '-f', 'flv', '-ar', '44100', '-t', duration, 'pipe:1']
    # actual size of the video is not known, so we must send it in chunks
    handler.protocol_version = 'HTTP/1.1'
    handler.send_response(200)
    handler.send_header('Transfer-Encoding', 'chunked')
    handler.send_header('Content-Type', 'video/x-flv')
    handler.end_headers()
    print('encoding video', flush=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
    chunkSize = 32 * 1024
    while True:
        chunk = proc.stdout.read(chunkSize)
        length = len(chunk)
        output = bytes('%X\r\n' % length, 'ascii')
        output += chunk
        output += bytes('\r\n', 'ascii')
        handler.wfile.write(output)
        if length == 0:
            break
    print('done encoding', flush=True)

##### Request Handler #####

# Serves a local file
def serve_file(handler, filename, contentType=None):
    print('serving file ' + filename)
    try:
        with open('./' + filename, 'rb') as f:
            handler.send_response(200)
            if contentType:
                handler.send_header('Content-type', contentType)
                handler.end_headers()
            handler.wfile.write(f.read())
    except FileNotFoundError:
        raise Error404
    except:
        raise Error500
    return

# Forwards a request to an external site and returns the result back to the client
def forward_request(handler, domain, path, params):
    url = 'https://' + domain + path
    r = requests.get(url, params)
    handler.send_response(r.status_code)
    handler.wfile.write(r.content)

# Files that can be served to the client, with their associated MIME types
allowedFiles = {
    '/player_flv_maxi.swf':     'application/x-shockwave-flash',
    '/jw_flvplayer_32.swf':     'application/x-shockwave-flash',
    '/tubescraper_logo_64.png': 'image/x-png',
    '/search_icon.png':         'image/x-png',
    '/favicon.ico':             'image/x-icon',
    '/style.css':               'text/css',
    '/ie6.css':                 'text/css',
    '/scripts.js':              'text/javascript',
}

class MyRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            arr = self.path.split('?')
            path  = arr[0]
            query = arr[1] if len(arr) > 1 else None
            params = urllib.parse.parse_qs(query) if len(arr) > 1 else {}
            # Home page
            if path == '/':
                serve_main_page(self)
            # Files
            elif path in allowedFiles:
                serve_file(self, path, allowedFiles[path])
            # Flash video converter
            elif path == '/flvconvert.flv':
                if False:
                    serve_file(self, 'test.flv')
                else:
                    query = self.path.split('?', 1)[1]
                    if not query.startswith('src='):
                        raise Error404
                    url = query[4:]
                    print('url: %s' % url)
                    serve_flv(self, url)
            # Results page
            elif path == '/results':
                if 'search_query' in params:
                    serve_results_page(self, params, query)
                else:
                    serve_main_page(self)
            # Watch page
            elif path == '/watch':
                if 'v' in params:
                    if 'list' in params:
                        plist = params['list'][0]
                    else:
                        plist = None
                    serve_watch_page(self, params['v'][0], plist)
                else:
                    raise Error404
            elif path.startswith('/shorts/'):
                serve_watch_page(self, path.split('/')[2])
            elif path == '/comments':
                serve_comments_page(self, params)
            # Playlist page
            elif path == '/playlist':
                serve_playlist_page(self, params)
            # Channel page
            elif path.startswith('/channel/') or path.startswith('/@'):
                serve_channel_page(self, path, params)
            # Forward caption requests to YouTube. (These can't be cross-origin for some reason)
            elif path == '/api/timedtext':
                forward_request(self, 'youtube.com', path, params)
            else:
                raise Error404('unknown path ' + path)
        except Error404:
            serve_page(self, 404, '<html><body><p>404 Not Found</p></body></html>'.encode(encoding='utf-8'))
            raise
        except Exception:
            serve_page(self, 500, '<html><body><p>500 Internal Server Error</p></body></html>'.encode(encoding='utf-8'))
            raise

port = int(sys.argv[1]) if len(sys.argv) >= 2 else 80
with http.server.ThreadingHTTPServer(('', port), MyRequestHandler) as server:
    server.serve_forever()
