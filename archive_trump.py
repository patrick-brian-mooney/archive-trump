#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""This script uses the Twitter streaming API to wait for tweets by Donald Trump,
then causes them to be archived at the Internet Archive, hopefully before The
Donald deletes them.

First steps here were based partly on a reading of the quesiton and answers at 
http://stackoverflow.com/a/38192468/5562328 -- thanks kmario23 for pointing me
in the right direction.

This program is free software, licensed under the GPL, either version 3, or (at
your choice) any later version, and you are welcome to modify or redistribute
it, subject to certain requirements; see the file LICENSE.md for more info.
"""


import time, json, requests, sys

from tweepy.streaming import StreamListener                     # http://www.tweepy.org
from tweepy import OAuthHandler
from tweepy import Stream
from http.client import IncompleteRead

import pid                                                      # https://pypi.python.org/pypi/pid/


import social_media as sm                                       # https://github.com/patrick-brian-mooney/python-personal-library/
from social_media_auth import Trump_client                      # Unshared module that contains my authentication constants


consumer_key = Trump_client['consumer_key']
consumer_secret = Trump_client['consumer_secret']
access_token = Trump_client['access_token']
access_token_secret = Trump_client['access_token_secret']

# Trump_twitter_accounts = {'814046047546679296': 'false_trump',}
Trump_twitter_accounts = {'25073877': 'realDonaldTrump', '822215679726100480': 'POTUS'}
archiving_url_prefixes = ['http://web.archive.org/save/']

last_tweet_id_store = '/home/patrick/Documents/programming/python_projects/archive-trump/last_tweet'

debugging = True


def get_tweet_urls(username, id):
    """Return all of the relevant URLs of the specified tweet. Currently, this
    just means that the http:// and https:// versions are returned.
    """
    ret = "twitter.com/%s/status/%s" % (username, id)
    return "http://" + ret, "https://" + ret

def archive_tweet(screen_name, id, text):
    """Have the Internet Archive (and in the future, perhaps, other archives) save
    a copy of this tweet. 
    """
    if debugging: print("New tweet from %s: %s" % (screen_name, text))
    for which_url in get_tweet_urls(screen_name, id):
        if debugging: print("\narchiving URL %s" % which_url)
        for which_prefix in archiving_url_prefixes:
            if debugging: print("    ... archiving using prefix %s" % which_prefix)
            req = requests.get(which_prefix + which_url)
            for the_item in req.iter_content(chunk_size=100000): pass   # read the file to make the IArchive archive it.
    try:
        store = open("%s.%s" % (last_tweet_id_store, screen_name), mode="r+")
    except FileNotFoundError:
        with open("%s.%s" % (last_tweet_id_store, screen_name), mode="w") as store:
            store.write('-1')
        store = open("%s.%s" % (last_tweet_id_store, screen_name), mode="r+")
    try:
        if int(store.read()) < int(id):     # If this is a newer tweet we're getting, store its ID as the newest tweet seen.
            store.seek(0)
            store.write(id)
    except (TypeError, ValueError):
        store.seek(0)
        store.write(id)
    store.close()


class TrumpListener(StreamListener):
    """Donald Trump is an abusive, sexist, racist, jingoistic pseudo-fascist. It's
    best to avoid actually paying attention to what he writes. Let's create a
    bot to listen for us.
    """
    def on_data(self, data):
        data = json.loads(data)
        if data['user']['id_str'] in Trump_twitter_accounts:        # If it's one of the accounts we're watching, archive it.
            archive_tweet(data['user']['screen_name'], data['id_str'], data['text'])
        return True
    def on_error(self, status):
        print("ERROR: %s" % status)


# This next group of functions handles the downloading, processing, and storing of The Donald's tweets.
def get_new_tweets(screen_name, oldest=-1):
    """Get those tweets newer than the tweet whose ID is specified as the OLDEST
    parameter from the account SCREEN_NAME.
    """
    the_API = sm.get_new_twitter_API(Trump_client)
    # get most recent tweets (200 is maximum possible at once)
    new_tweets = the_API.user_timeline(screen_name=screen_name, count=200)
    ret = new_tweets.copy()

    oldest_tweet = ret[-1].id - 1  # save the id of the tweet before the oldest tweet

    # keep grabbing tweets until there are no tweets left
    while len(new_tweets) > 0 and oldest < new_tweets[0].id:
        if debugging: print("getting all tweets before ID #%s" % (oldest_tweet))
        new_tweets = the_API.user_timeline(screen_name=screen_name, count=200, max_id=oldest_tweet)
        ret.extend(new_tweets)
        oldest_tweet = ret[-1].id - 1
        if debugging: print("    ...%s tweets downloaded so far" % (len(ret)))
    return [t for t in ret if (t.id > oldest)]

def startup():
    """Perform startup tasks. Currently, this means:
        
        1. archive any tweets we may have missed between now and whenever we last
           stopped running.
        2. that's it. Nothing else.
    """
    if debugging: print('Starting up...')
    for id, username in Trump_twitter_accounts.items():
        try:
            with open("%s.%s" % (last_tweet_id_store, username)) as store:
                newest_id = int(store.read())
        except FileNotFoundError:
            with open("%s.%s" % (last_tweet_id_store, username), mode="w") as store:
                store.write("-1")
            newest_id = -1
        for tw in [t for t in get_new_tweets(screen_name=username, oldest=newest_id) if t.id > newest_id]:
            archive_tweet(tw.user.screen_name, tw.id_str, tw.text)
            time.sleep(1)


if __name__ == '__main__':
    try:
        with pid.PidFile(piddir='.'):
            startup()
            l = TrumpListener()
            auth = OAuthHandler(consumer_key, consumer_secret)
            auth.set_access_token(access_token, access_token_secret)
            if debugging: print("... OK, we're set up, and about to watch %s" % ', '.join(Trump_twitter_accounts))
            while True:
                try:
                    stream = Stream(auth, l)
                    stream.filter(follow=Trump_twitter_accounts, stall_warnings=True)
                except IncompleteRead as e:
                    # Sleep some before trying again.
                    time.sleep(15)
                    continue
                except KeyboardInterrupt:
                    stream.disconnect()
                    break
    except pid.PidFileError:
        if debugging: print("Already running! Quitting ...")
        sys.exit()