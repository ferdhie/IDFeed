#!/usr/bin/env python

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext.webapp import util

from django.utils import simplejson
from common import login_required, BaseRequestHandler
import common
import console
import models

_DEBUG = True
if _DEBUG:
    import cgitb
    cgitb.enable()


class MainHandler(BaseRequestHandler):
    def get(self):
        links = []
        links2 = []
        for link in models.Link.gql("ORDER BY priority DESC"):
            if len(links2) == 3:
                links.append(links2)
                links2 = [link]
            else:
                links2.append(link)
        if links2:
            links.append(links2)

        if self.is_mobile_browser() or self.request.get('m'):
            self.generate( 'index_mobile.html', locals() )
        else:
            self.generate( 'index.html', locals() )


class FeedHandler(BaseRequestHandler):
    def get(self, param):
        k = db.Key(param)
        link = models.Link.get(k)
        if link:
            self.generate('feed_detail.html', locals())
        else:
            self.error(404)
            self.response.out.write('404 Not Found')

class SuggestPage(BaseRequestHandler):
    def get(self):
        self.generate( 'suggest.html', locals() )

    def post(self):
        url = self.request.get('url', '').strip()
        error = None
        success = False
        if url:
            if not url.startswith('http'):
                url = 'http://' + url
            l = models.SuggestLink.get_by_key_name(url)
            if l:
                l.count += 1
                l.put()
                success = True
            else:
                try:
                    result = urlfetch.fetch(url)
                    if result.status_code == 200:
                        l = models.SuggestLink(key_name=url, url=url, count=1)
                        l.put()
                        success = True
                    else:
                        error = '''Maaf, URL yang anda masukkan tidak tersedia'''
                except:
                    error = '''Maaf, URL yang anda masukkan tidak tersedia'''
        else:
            error = '''Maaf, mohon isikan URL untuk feed yang akan anda sarankan'''

        self.generate( 'suggest.html', locals() )


class AjaxFetch(BaseRequestHandler):
    def get(self):
        key = self.request.get('key')
        if key:
            k = db.Key(key)
            link = models.Link.get(k)
            if link:
                def callback(link, r):
                    self.generate( 'fetch_link.html', locals() )
                link.fetch(callback).wait()


class AjaxShort(BaseRequestHandler):
    def get(self):
        url = self.request.get('url')
        callback = self.request.get('_callback')
        if url and url.startswith('http'):
            u = models.ShortLink.get_or_insert('url-'+url, url=url)
            shorturl = u.shorten()
            self.generate( {'url':url, 'shorturl':shorturl}, callback )
        else:
            self.generate( {'error':'Invalid URL'} )


class UpdateHandler(BaseRequestHandler):
    def get(self):
        self.response.headers['Content-type'] = 'text/plain; charset=UTF-8'

        def callback(link, r):
            self.response.out.write( "result: url=%s, len=%s\n" % (link.url, len(r)) )

        last_key = memcache.get('last_update')
        rpcs = []
        if last_key:
            for link in models.Link.gql( 'WHERE __key__ > :1', db.Key(last_key) ).fetch(1):
                rpcs.append( link.fetch(callback) )
                last_key = str(link.key())

        if not last_key or not rpcs:
            for link in models.Link.all().fetch(1):
                rpcs.append( link.fetch(callback) )
                last_key = str(link.key())

        if last_key:
            memcache.set('last_update', last_key)

        for rpc in rpcs:
            rpc.wait()

        self.response.out.write("OK\n")


class LinkPage(BaseRequestHandler):
    @login_required
    def get(self, param):
        links = models.Link.gql("ORDER BY priority DESC")
        link = None
        if param == 'edit':
            key = self.request.get('key')
            if key:
                link = models.Link.get(db.Key(key))
        self.generate( 'link_list.html', locals() )

    @login_required
    def post(self, param):
        if param == 'update':
            if self.request.get('delete'):
                keys = [ db.Key(x) for x in self.request.get( 'keys', [], True ) if x ]
                if keys:
                    for link in models.Link.get(keys):
                        link.delete()
            else:
                url_new = self.request.get('url-new', '')
                home_new = self.request.get('home-new', '')
                title_new = self.request.get('title-new', '')
                descr_new = self.request.get('description-new', '')
                priority_new = self.request.get('priority-new', '')
                if url_new:
                    key = url_new
                    if key.startswith('http://'):
                        key = key[7:]
                    elif key.startswith('https://'):
                        key = key[8:]
                    try:
                        priority = int(priority_new)
                    except:
                        priority = 0

                    l = models.Link.get_or_insert(key, url=url_new, title=title_new, description=descr_new, homepage=home_new, priority=int(priority))

                for k in self.request.get( 'updated', [], True ):
                    k = k.strip()
                    if not k:
                        continue
                    link = models.Link.get( db.Key(k) )
                    if link:
                        url = self.request.get('url-%s' % k)
                        if url:
                            link.url = url
                        title = self.request.get('title-%s' % k)
                        if title:
                            link.title = title
                        home = self.request.get('home-%s' % k)
                        if home:
                            link.homepage = home
                        descr = self.request.get('description-%s' % k)
                        if descr:
                            link.descr = descr

                        priority = self.request.get('priority-%s' % k)
                        if priority:
                            try:
                                priority = int(priority)
                            except:
                                priority = 0
                            link.priority = priority

                        if url or title or descr or home:
                            link.put()

        self.redirect('/links/?update=true')


def main():
    application = webapp.WSGIApplication([
        ('/', MainHandler),
        ('/feed/(.*)', FeedHandler),
        ('/update', UpdateHandler),
        ('/fetch', AjaxFetch),
        ('/url', AjaxShort),
        ('/suggest', SuggestPage),
        ('/console', console.ConsolePage),
        ('/links/(.*)', LinkPage),
        ], debug=_DEBUG)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
