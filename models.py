#!/usr/bin/env python

import logging
import pickle
import calendar
import time
import datetime
import re
from urllib import quote, urlencode

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import urlfetch

from django.utils.html import strip_tags
from django.utils import simplejson
import feedparser

debug = 0

feedparser.registerDateHandler(lambda s:time.strptime(s[:-6], "%a , %d %b %Y %H:%M:%S"))

_query_cache = {}

def gql(cls, clause, *args, **kwds):
    try:
        query_string = 'SELECT * FROM %s %s' % (cls.kind(), clause)
    except AttributeError:
        query_string = 'SELECT * FROM %s %s' % (cls, clause)
    query = _query_cache.get(query_string)
    if query is None:
        logging.info("query_cache: %s -> MISS" % query_string)
        _query_cache[query_string] = query = db.GqlQuery(query_string)
    else:
        logging.info("query_cache: %s  -> HIT" % query_string)
    query.bind(*args, **kwds)
    return query

class ShortLink(db.Model):
    url = db.LinkProperty()
    shorturl = db.LinkProperty()

    def shorten(self):
        if self.shorturl:
            return self.shorturl

        if not re.match('http://', str(self.url)):
            raise Exception('URL must start with "http://"')

        result = urlfetch.fetch(url='http://goo.gl/api/url',
                                payload='url=%s' % quote(str(self.url)),
                                method=urlfetch.POST,
                                headers={'User-Agent':'toolbar'})
        j = simplejson.loads(result.content)
        if 'short_url' not in j:
            try:
                from pprint import pformat
                j = pformat(j)
            except ImportError:
                j = j.__dict__
            raise Exception('Didn\'t get a correct-looking response. How\'s it look to you?\n\n%s'%j)

        self.shorturl = j['short_url']
        self.put()

        return self.shorturl


class SuggestLink(db.Model):
    url = db.LinkProperty()
    count = db.IntegerProperty(default=0)

class Link(db.Model):
    url = db.LinkProperty()
    homepage = db.LinkProperty()
    title = db.StringProperty()
    description = db.TextProperty()
    data = db.BlobProperty()
    last_mod = db.TextProperty()
    priority = db.IntegerProperty(default=0)

    fetch_callback = None
    rpc = None

    def fetch(self, callback):
        self.fetch_callback = callback
        self.rpc = urlfetch.create_rpc()
        self.rpc.callback = self.rpc_result
        logging.info( "fetch: %s - %s" % (self.url, self.last_mod) )

        headers = {}
        if self.last_mod:
            headers['If-Modified-Since'] = self.last_mod

        urlfetch.make_fetch_call(self.rpc, self.url, headers=headers)
        return self.rpc

    def entries(self):
        r = memcache.get( self.url )
        if r is None:
            logging.info('%s MISS' % self.url)
            if self.data is not None:
                r = pickle.loads(str(self.data))
                if r:
                    memcache.set( self.url, r, 86400 )
        if r is None:
            return []
        return r

    def rpc_result(self):
        result = self.rpc.get_result()
        if result.status_code == 304:
            if self.data:
                r = pickle.loads(str(self.data))
            else:
                r = []
            self.fetch_callback(self, r)
            return

        if result.status_code != 200:
            self.fetch_callback(self, [])
            return

        self.last_mod = result.headers.get('last-modified')
        logging.info( 'rpc_result: %s,%s,%s' % (self.url, result.status_code, self.last_mod) )

        feedparser._debug = debug
        feed = feedparser.parse(result.content)

        if not self.title:
            self.title = strip_tags(feed.feed.title)
        if not self.description:
            self.description = strip_tags(feed.feed.description)

        ids = {}
        if self.data:
            r = pickle.loads(str(self.data))
            for i in r:
                ids[i['id']] = 1
        else:
            r = []

        for entry in feed.entries:
            link = entry.get('link', '')
            id = entry.get('id', link)
            if ids.has_key( id ):
                continue

            title = strip_tags(entry.get('title', ''))
            description = entry.get('description')
            if not description:
                description = entry.get('summary', '')
            pubdate = entry.get('date_parsed')
            if not pubdate:
                pubdate = time.gmtime()
            timestamp = calendar.timegm(pubdate)
            date = datetime.datetime( *pubdate[:6] )
            r.append(dict(id=id,title=title,link=link,descr=description,pubdate=date,timestamp=timestamp))
            ids[id]=1

        r = sorted( r, lambda x,y:y['timestamp']-x['timestamp'] )[0:20]
        self.data = db.Blob( pickle.dumps(r) )
        self.put()

        memcache.set( self.url, r, 86400 )
        self.fetch_callback(self, r)
