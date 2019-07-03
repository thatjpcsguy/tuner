#!/usr/local/bin/python2

from bs4 import BeautifulSoup
#from twilio.rest import TwilioRestClient 
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

import PTN

import urllib3


reload(sys)
sys.setdefaultencoding('utf-8')

config = ConfigParser.RawConfigParser(allow_no_value=True)
config.read('tuner.conf')

#twilio = TwilioRestClient(config.get("twilio", "key"), config.get("twilio", "token"))

episode_info_regex = re.compile(ur'(S?([0-9]{1,2})[x|E]([0-9]{1,2}))', re.IGNORECASE)
episode_id_regex = re.compile(ur'/ep/([0-9]*)/', re.IGNORECASE)
episode_magnet_regex = re.compile(ur' href="(.*)" rel', re.IGNORECASE)

transmission_server = config.get("transmission", "host") + "/ui/rpc"

db = None


def get_db():
    global db
    if db is None:
        db = _mysql.connect(host=config.get("db", "host"), user=config.get("db", "user"), passwd=config.get("db", "passwd"), db=config.get("db", "db"))
    return db


def update_available_shows():
    db = get_db()
    r = requests.get(config.get("eztv", "host") + '/showlist/')
    soup = BeautifulSoup(r.text, "lxml")


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

        try:
            db.query("INSERT INTO shows (`show_id`, `name`, `url`, `path`, `status`, `download`) VALUES ('%s', '%s', '%s', '%s', '%s', 0) ON DUPLICATE KEY UPDATE status = '%s', url = '%s'" % (show_id, db.escape_string(str(name)), url, path, db.escape_string(status), db.escape_string(status), url))
        except:
            pass


def update_available_eps(url, show_id):
    db = get_db()
    ep = requests.get(config.get("eztv", "host") + url)
    eps = BeautifulSoup(ep.text, "lxml")

    for episode in eps.find_all('tr'):
        ep_string = str(episode.find('a', class_="epinfo"))
        parsed_data = PTN.parse(ep_string)
        quality = parsed_data['quality'] if 'quality' in parsed_data else 'Unknown'
        resolution = parsed_data['resolution'] if 'resolution' in parsed_data else 'Unknown'

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
        if magnet is not None:
            magnet = db.escape_string(re.findall(episode_magnet_regex, str(magnet))[0])
            db.query("INSERT INTO episodes (`show_id`, `episode_id`, `number`, `season`, `magnet`, `downloaded`, `quality`, `resolution`) VALUES ('%s', '%s', '%s', '%s', '%s', 0, '%s', '%s') ON DUPLICATE KEY UPDATE magnet = '%s', quality = '%s', resolution = '%s'" % (
                show_id, episode_id, number, season, magnet, quality, resolution, magnet, quality, resolution))




def check_new_eps_active():
    db = get_db()
    db.query("SELECT * FROM shows WHERE `download` = 1")
    res = db.store_result()
    i = res.fetch_row(how=1)
    while i:
        update_available_eps(i[0]['url'], i[0]['show_id'])
        i = res.fetch_row(how=1)


def add(id):
    db = get_db()
    db.query("UPDATE shows SET download = 1 WHERE show_id = %s" % (id))


def download_missing():
    db = get_db()
    csrf = requests.get(transmission_server)
    soup = BeautifulSoup(csrf.text, "lxml")
    if soup.code is None:
        exit()
    session = soup.code.get_text().split(":")[1].strip()

    headers = {'X-Transmission-Session-Id': session}

    db.query("SELECT s.show_id, season, number, path, MIN(magnet) magnet, s.name show_name, MIN(e.episode_id) episode_id FROM episodes e JOIN shows s ON e.show_id = s.show_id  WHERE `download` = 1 GROUP BY s.show_id, season, number, s.name, path HAVING MAX(downloaded) = 0")
    res = db.store_result()
    i = res.fetch_row(how=1)
    
    while i:
        payload = {
                "method": "torrent-add",
                "arguments": {
                    "paused": False,
                    "filename": i[0]['magnet'],
                    "download-dir": config.get("transmission", "dir") + "/%s/season %s/" % (i[0]['path'].replace("-", " "), i[0]['season'])
                }
            }
        r = requests.post(transmission_server, data=json.dumps(payload), headers=headers, verify=False)
        if r.status_code == 200:
            db.query("UPDATE episodes SET downloaded = 1 WHERE episode_id = %s" % (i[0]['episode_id']))

        i = res.fetch_row(how=1)


def list_quality(show_id, season=False):
    db = get_db()
    
    db.query("SELECT max(episode_id) episode_id, season, number, quality, resolution, downloaded, magnet FROM episodes e WHERE show_id = %s %s GROUP BY season, number, resolution, quality, episode_id, magnet ORDER BY number ASC, episode_id DESC" % (show_id, 'AND season = %s' % season if season else ''))
    
    res = db.store_result()
    i = res.fetch_row(how=1)
    
    while i:
        name = i[0]['magnet'].split('amp;dn=')[1].split('&amp;')[0]
        info = PTN.parse(name)
        print info
        print '%s: s%se%s %s %s %s' % (i[0]['episode_id'], i[0]['season'], i[0]['number'], i[0]['resolution'], i[0]['quality'], name)
        
        i = res.fetch_row(how=1)


def search(name):
    db = get_db()
    
    db.query("SELECT show_id, name FROM shows WHERE name LIKE '%%%s%%'" % (name))
    
    res = db.store_result()
    i = res.fetch_row(how=1)
    
    while i:
        print '%s: %s' % (i[0]['show_id'], i[0]['name'])
        
        i = res.fetch_row(how=1)


def download_id(episode_id):
    db = get_db()
    csrf = requests.get(transmission_server)
    soup = BeautifulSoup(csrf.text, "lxml")
    if soup.code is None:
        print "Cannot connect to Transmission"
        exit()
    session = soup.code.get_text().split(":")[1].strip()

    headers = {'X-Transmission-Session-Id': session}

    db.query("SELECT s.show_id, season, number, path, magnet, s.name show_name, e.episode_id episode_id FROM episodes e JOIN shows s ON e.show_id = s.show_id  WHERE episode_id = '%s'" % (episode_id))
    res = db.store_result()
    i = res.fetch_row(how=1)


    print i[0]['show_name'] + ' - Season ' + str(i[0]['season'])+', Episode ' + str(i[0]['number'])
    payload = {
        "method": "torrent-add",
        "arguments": {
            "paused": False,
            "filename": i[0]['magnet'],
            "download-dir": config.get("transmission", "dir") + "/%s/season %s/" % (i[0]['path'].replace("-", " "), i[0]['season'])
        }
    }
    r = requests.post(transmission_server, data=json.dumps(
        payload), headers=headers, verify=False)
    if r.status_code == 200:
        print "downloading"
        db.query("UPDATE episodes SET downloaded = 1 WHERE episode_id = %s" % (i[0]['episode_id']))
    else:
        print "failed"



if __name__ == '__main__':
    if sys.argv[1] == "--auto":
        update_available_shows()
        check_new_eps_active()
        download_missing()

    if sys.argv[1] == "--got":
        update_available_eps('/shows/481/game-of-thrones/', 481)
        list_quality(481, 8)
        download_missing()

    if sys.argv[1] == "--dl":
        download_id(sys.argv[2])

    if sys.argv[1] == "--search":
        search(sys.argv[2])

    if sys.argv[1] == "--list":
        if len(sys.argv) > 3:
            list_quality(sys.argv[2], sys.argv[3])
        else:
            list_quality(sys.argv[2])

    if sys.argv[1] == "--add":
        add(sys.argv[2])

    if '--help' in sys.argv:
        print("""./tv.py
    --got
    --search <name>
    --list <show_id> <season>
    --dl <episode_id>
    --add <show_id>
    --auto""")
