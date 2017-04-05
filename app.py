#!/usr/local/bin/python

from bs4 import BeautifulSoup
from twilio.rest import TwilioRestClient 
import requests
import _mysql
import re
import json
import sys
import ConfigParser
import urllib
from lxml import etree
from lxml.etree import fromstring
from lxml import objectify


import urllib3


reload(sys)
sys.setdefaultencoding('utf-8')

config = ConfigParser.RawConfigParser(allow_no_value=True)
config.read('tuner.conf')

twilio = TwilioRestClient(config.get("twilio", "key"), config.get("twilio", "token"))

episode_info_regex = re.compile(ur'(S?([0-9]{1,2})[x|E]([0-9]{1,2}))', re.IGNORECASE)
episode_id_regex = re.compile(ur'/ep/([0-9]*)/', re.IGNORECASE)
episode_magnet_regex = re.compile(ur'href="(.*)" class', re.IGNORECASE)

transmission_server = "http://" + config.get("transmission", "host") + "/ui/rpc"

db = None


def get_db():
    global db
    if db is None:
        before_request()
    return db


def update_available_shows():
    db = get_db()
    r = requests.get(config.get("eztv", "host") + '/showlist/')
    soup = BeautifulSoup(r.text)


    for row in soup.find_all('tr'):
        
        name = ''
        url = ''
        status = ''
        for a in row.find_all('a', href=True):
            url =  str(a['href'])
            name =  str(a.get_text())

        info = url.strip('/').split('/')

        if len(info) == 3:
            show_id = info[1]
            path = info[2]
        else:
            continue

        for font in row.find_all('font'):
            status = font.get_text()

        #print info
        try:
            db.query("INSERT INTO shows (`show_id`, `name`, `url`, `path`, `status`, `download`) VALUES ('%s', '%s', '%s', '%s', '%s', 0) ON DUPLICATE KEY UPDATE status = '%s', url = '%s'" % (show_id, db.escape_string(str(name)), url, path, db.escape_string(status), db.escape_string(status), url))
        except:
            #print "Error inserting show"
            pass

def update_available_eps(url, show_id):
    db = get_db()
    ep = requests.get(config.get("eztv", "host") + url)
    eps = BeautifulSoup(ep.text)

    for episode in eps.find_all('tr'):
        try:
            ep_string = str(episode.find('a', class_="epinfo"))
            info = re.findall(episode_info_regex, ep_string)
            if len(info) > 0:
                season = info[0][1]
                number = info[0][2]
            else:
                continue

            ep_id = re.findall(episode_id_regex, ep_string)
            if len(ep_id) > 0:
                episode_id = ep_id[0] 

            magnet = episode.find('a', class_="magnet")
            magnet = db.escape_string(re.findall(episode_magnet_regex, str(magnet))[0])

            db.query("INSERT INTO episodes (`show_id`, `episode_id`, `number`, `season`, `magnet`, `downloaded`) VALUES ('%s', '%s', '%s', '%s', '%s', 0) ON DUPLICATE KEY UPDATE magnet = '%s'" % (show_id, episode_id, number, season, magnet, magnet))
        except:
            #print "unable to insert episode"
            pass


def check_new_eps_active():
    db = get_db()
    db.query("SELECT * FROM shows WHERE `download` = 1")
    res = db.store_result()
    i = res.fetch_row(how=1)
    while i:
        update_available_eps(i[0]['url'].replace('eztv.it', 'eztv-proxy.net'), i[0]['show_id'])
        i = res.fetch_row(how=1)

def download_missing():
    db = get_db()
    csrf = requests.get(transmission_server)
    soup = BeautifulSoup(csrf.text)
    session = soup.code.get_text().split(":")[1].strip()

    headers = {'X-Transmission-Session-Id': session}

    db.query("SELECT *, s.name show_name FROM episodes e JOIN shows s ON e.show_id = s.show_id  WHERE `download` = 1 GROUP BY s.show_id, season, number HAVING MAX(downloaded) = 0")
    res = db.store_result()
    i = res.fetch_row(how=1)
    
    downloading = ""
    while i:
        downloading += i[0]['show_name']+ ' - Season ' + str(i[0]['season'])+', Episode '+ str(i[0]['number']) + "\n"
        payload = {
                "method": "torrent-add",
                "arguments": {
                    "paused": False,
                    "filename": i[0]['magnet'],
                    "download-dir": config.get("transmission", "dir") + "/%s/season %s/" % (i[0]['path'].replace("-", " "), i[0]['season'])
                }
            }
        #print payload
        r = requests.post(transmission_server, data=json.dumps(payload), headers=headers)
        if r.status_code == 200:
            db.query("UPDATE episodes SET downloaded = 1 WHERE show_id = %s AND number = %s and season = %s" % (i[0]['show_id'], i[0]['number'], i[0]['season']))

        i = res.fetch_row(how=1)

    if downloading:
        print downloading
        # for number in config.get("twilio", "to").split(","):
            
            # send_sms(number.strip(), downloading)


# def send_sms(to, body):
#     try:
#         twilio.messages.create(
#                 to=to, 
#                 from_=config.get("twilio", "from"),
#                 body=body
#             )
#     except:
#         print "could not send sms"
#         pass



if __name__ == '__main__':
    elif sys.argv[1] == "update":
        update_available_shows()
        check_new_eps_active()
        download_missing()



