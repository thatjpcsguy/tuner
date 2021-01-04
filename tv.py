#!/usr/local/bin/python3

from bs4 import BeautifulSoup
import requests
import re
import json
import sys
import configparser
import urllib.request, urllib.parse, urllib.error

import PTN

import pymysql


config = configparser.RawConfigParser(allow_no_value=True)
config.read('tuner.conf')

#twilio = TwilioRestClient(config.get("twilio", "key"), config.get("twilio", "token"))

episode_info_regex = re.compile(r'(S?([0-9]{1,2})[x|E]([0-9]{1,2}))', re.IGNORECASE)
episode_id_regex = re.compile(r'/ep/([0-9]*)/', re.IGNORECASE)
episode_magnet_regex = re.compile(r' href="(.*)" rel', re.IGNORECASE)

transmission_server = config.get("transmission", "host") + "/transmission/rpc"
deluge_server = config.get("deluge", "host") + "/json"


db = None
cursor = None
def get_db():
    global db
    global cursor
    if db is None:
        #print("Connecting to database...")
        db = pymysql.connect(host=config.get("db", "host"), user=config.get("db", "user"), passwd=config.get("db", "passwd"), db=config.get("db", "db"), cursorclass=pymysql.cursors.DictCursor)

    if cursor is None:
        #print("Creating cursor object...")
        cursor = db.cursor()

    # print("Database connection successful!")
    return db, cursor


def update_available_shows():
    db, cursor = get_db()
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

        
        cursor.execute("INSERT INTO shows (`show_id`, `name`, `url`, `path`, `status`, `download`) VALUES (%s, %s, %s, %s, %s, 0) ON DUPLICATE KEY UPDATE status = %s, url = %s", (show_id, db.escape_string(str(name)), url, path, db.escape_string(status), db.escape_string(status), url, ))
        db.commit()


def update_available_eps(url, show_id):
    db, cursor = get_db()
    #print(url)

    ep = requests.get('%s%s' % (config.get("eztv", "host"), url))
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
            magnet = magnet['href']
            cursor.execute("INSERT INTO episodes (`show_id`, `episode_id`, `number`, `season`, `magnet`, `downloaded`, `quality`, `resolution`) VALUES (%s, %s, %s, %s, %s, 0, %s, %s) ON DUPLICATE KEY UPDATE magnet = %s, quality = %s, resolution = %s", (show_id, episode_id, number, season, magnet, quality, resolution, magnet, quality, resolution, ))
            
    db.commit()



def check_new_eps_active(show_id=False):
    db, cursor = get_db()
    if show_id:
        cursor.execute("SELECT * FROM shows WHERE `show_id` = %s", (show_id, ))
    else:
        if '--airing' in sys.argv:
            cursor.execute("SELECT * FROM shows WHERE `download` = 1 AND status LIKE '%Airing%'")
        else:
            cursor.execute("SELECT * FROM shows WHERE `download` = 1")

    rows = cursor.fetchall()
    for row in rows:
        update_available_eps(row['url'], row['show_id'])


def add(id):
    db, cursor = get_db()
    cursor.execute("UPDATE shows SET download = 1 WHERE show_id = %s" % (id))
    db.commit()


def download_deluge(magnet, directory):
    deluge_server = 'http://10.1.1.11:8112/json'

    cookies = None
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}

    payload = {"id": 1, "method": "auth.login", "params": ["deluge"]}
    response = requests.post(deluge_server, data=json.dumps(
        payload), headers=headers, cookies=cookies)

    cookies = response.cookies

    payload = json.dumps({"id": 2, "method": "webapi.add_torrent", "params": [magnet, {
                         "move_completed_path": directory, "move_completed": True, "download_path": "/Volumes/Orange/Incomplete"}]})

    response = requests.post(deluge_server, data=payload,
                             headers=headers, cookies=cookies)

    return response.status_code

def download_transmission(magnet, directory):
    csrf = requests.get(transmission_server)
    soup = BeautifulSoup(csrf.text, "lxml")
    if soup.code is None:
        exit()
    session = soup.code.get_text().split(":")[1].strip()
    headers = {'X-Transmission-Session-Id': session}
    payload = {
        "method": "torrent-add",
        "arguments": {
            "paused": False,
            "filename": magnet,
            "download-dir": directory
        }
    }
    r = requests.post(transmission_server, data=json.dumps(
        payload), headers=headers, verify=False)

    return r.status_code



def download_missing():
    db, cursor = get_db()
    cursor.execute("SELECT s.show_id, season, number, path, MIN(magnet) magnet, s.name show_name, MIN(e.episode_id) episode_id FROM episodes e JOIN shows s ON e.show_id = s.show_id  WHERE `download` = 1 GROUP BY s.show_id, season, number, s.name, path HAVING MAX(downloaded) = 0")
    
    rows = cursor.fetchall()
    for row in rows:
        download_path = "%s/%s/season %s/" % (config.get("transmission", "dir"), row['path'].replace("-", " "), row['season'])

        status = download_transmission(row['magnet'], download_path)
        
        if status == 200:
            cursor.execute("UPDATE episodes SET downloaded = 1 WHERE episode_id = %s", (row['episode_id'], ))
            db.commit()


def list_quality(show_id, season=False):
    db, cursor = get_db()
    cursor.execute("SELECT max(episode_id) episode_id, season, number, quality, resolution, downloaded, magnet FROM episodes e WHERE show_id = %s %s GROUP BY season, number, resolution, quality, episode_id, magnet ORDER BY number ASC, episode_id DESC" % (show_id, 'AND season = %s' % season if season else ''))
    
    rows = cursor.fetchall()
    for row in rows:
        try:
            name = row['magnet'].split('amp;dn=')[1].split('&amp;')[0]
        except:
            name = 'Unknown'
        info = PTN.parse(name)
        print(info)
        print(('%s: s%se%s %s %s %s' % (row['episode_id'], row['season'], row['number'], row['resolution'], row['quality'], name)))



def search(name):
    db, cursor = get_db()
    cursor.execute("SELECT show_id, name FROM shows WHERE name LIKE '%%%s%%'" % name)
    
    rows = cursor.fetchall()
    for row in rows:
        print(('%s: %s' % (row['show_id'], row['name'])))



def download_id(episode_id):
    db, cursor = get_db()

    csrf = requests.get(transmission_server)
    soup = BeautifulSoup(csrf.text, "lxml")
    if soup.code is None:
        print("Cannot connect to Transmission")
        exit()
    session = soup.code.get_text().split(":")[1].strip()

    headers = {'X-Transmission-Session-Id': session}

    cursor.execute("SELECT s.show_id, season, number, path, magnet, s.name show_name, e.episode_id episode_id FROM episodes e JOIN shows s ON e.show_id = s.show_id  WHERE episode_id = '%s'" % (episode_id))
    rows = cursor.fetchall()

    for row in rows:
        #print('%s - Season %s, Episode %s' % (row['show_name'], row['season'], row['number']))
        payload = {
            "method": "torrent-add",
            "arguments": {
                "paused": False,
                "filename": row['magnet'],
                "download-dir": "%s/%s/season %s/" % (config.get("transmission", "dir"), row['path'].replace("-", " "), row['season'])
            }
        }
        r = requests.post(transmission_server, data=json.dumps(
            payload), headers=headers, verify=False)
        if r.status_code == 200:
            #print("downloading")
            cursor.execute("UPDATE episodes SET downloaded = 1 WHERE episode_id = %s", (row['episode_id'], ))
            db.commit()
        else:
            print("download failed")



if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == "--auto":
            #print("Update available shows")
            update_available_shows()
            #print("Checking if new episodes are available")
            check_new_eps_active()
            #print("Downloading new episodes")
            download_missing()

        if '--download' in sys.argv or '--dl' in sys.argv:
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
            check_new_eps_active(sys.argv[2])
            download_missing()


        if '--help' in sys.argv:
            print("""./tv.py
    --got
    --search <name>
    --list <show_id> <season>
    --dl <episode_id>
    --add <show_id>
    --auto""")

    db.close()
