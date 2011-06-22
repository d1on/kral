import datetime
import json
import re
import time
import urllib2
from celery.decorators import periodic_task,task
from celery.result import AsyncResult

from kral.utils import cache, push_data
from kral import settings

@task
def facebook(queries,**kwargs):
    if not cache.get('facebook_rate_limit_time'):
        cache.set('facebook_rate_limit_time',int(round(time.time())))
        cache.set('facebook_rate_limit','0')
    else:
        rate_limit_time = cache.get('facebook_rate_limit_time')
        current_time = int(round(time.time()))
        diff = int(current_time) - int(rate_limit_time)
        if diff >= 600:
            cache.set('facebook_rate_limit_time',int(round(time.time())))
            cache.set('facebook_rate_limit','0')
        else:
            task_ids = []
            for query in queries:
                cache_name = "facebookfeed_%s" % query
                if cache.get(cache_name):
                    previous_result = AsyncResult(cache.get(cache_name))
                    if previous_result.ready():
                        result = facebook_feed.delay(query)
                        cache.set(cache_name,result.task_id)
                        task_ids.append(result.get())
                else:
                    result = facebook_feed.delay(query)
                    cache.set(cache_name,result.task_id)
                    task_ids.append(result.get())
            return task_ids

@task        
def facebook_feed(query, **kwargs):
        logger = facebook_feed.get_logger(**kwargs)
        cache_name = "facebook_prevurl_%s" % query
        rate_limit = int(cache.get('facebook_rate_limit'))
        rate_limit += 1
        cache.set('facebook_rate_limit',rate_limit)
        if cache.get(cache_name):
            url = cache.get(cache_name)
        else:
            url = "https://graph.facebook.com/search?q=%s&type=post&limit=25&access_token=%s" % (query.replace('_','%20'),settings.FACEBOOK_API_KEY)
        try:
            data = json.loads(urllib2.urlopen(url).read())
            items = data['data']
            if data.get('paging'):
                prev_url = data['paging']['previous']
            else:
                prev_url = url
            task_ids = []
            for item in items:
                result = facebook_post.delay(item, query)
                task_ids.append(result.task_id)
            cache.set(cache_name,str(prev_url))
            return task_ids
        except urllib2.HTTPError, error:
            logger.error("Facebook API returned HTTP Error: %s - %s" % (error.code,url))
        except urllib2.URLError, error:
            logger.error("Facebook API returned URL Error: %s - %s" % (error,url))
   
@task
def facebook_post(item, query, **kwargs):
    logger = facebook_post.get_logger(**kwargs)
    time_format = "%Y-%m-%dT%H:%M:%S+0000"
    if item.has_key('message'):
        post_info = {
            "service" : 'facebook',
            "user" : {
                "name": item['from'].get('name'),
                "id": item['from']['id'],
            },
            "links" : [],
            "id" : item['id'],
            "text" : item['message'],
            "date": str(datetime.datetime.strptime(item['created_time'], time_format)),
        }
        url_regex = re.compile('(?:http|https|ftp):\/\/[\w\-_]+(?:\.[\w\-_]+)+(?:[\w\-\.,@?^=%&amp;:/~\+#]*[\w\-\@?^=%&amp;/~\+#])?')
        for url in url_regex.findall(item['message']):
            post_info['links'].append({ 'href' : url })
        post_info['user']['avatar'] = "http://graph.facebook.com/%s/picture" % item['from']['id']
        if item.get('to'):
            post_info['to_users'] = item['to']['data']
        if item.get('likes'):
            post_info['likes'] = item['likes']['count']
        if item.get('application'):
            post_info['application'] = item['application']['name']
        push_data(post_info, queue=query)
        return

# vim: ai ts=4 sts=4 et sw=4