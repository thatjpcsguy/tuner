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
from flask import Flask, g, url_for, render_template, jsonify
app = Flask(__name__)

reload(sys)
sys.setdefaultencoding('utf-8')

config = ConfigParser.RawConfigParser(allow_no_value=True)
config.read('tuner.conf')

twilio = TwilioRestClient(config.get("twilio", "key"), config.get("twilio", "token"))

episode_info_regex = re.compile(ur'(S?([0-9]{1,2})[x|E]([0-9]{1,2}))', re.IGNORECASE)
episode_id_regex = re.compile(ur'/ep/([0-9]*)/', re.IGNORECASE)
episode_magnet_regex = re.compile(ur'href="(.*)" title', re.IGNORECASE)

transmission_server = "http://" + config.get("transmission", "host") + "/transmission/rpc"

db = None

@app.before_request
def before_request():
    global db
    db = _mysql.connect(host=config.get("db", "host"), user=config.get("db", "user"), passwd=config.get("db", "passwd"), db=config.get("db", "db"))

@app.teardown_request
def teardown_request(exception):
    if db is not None:
        db.close()

def get_db():
    global db
    if db is None:
        before_request()
    return db


def update_available_shows():
    db = get_db()
    r = requests.get('https://eztv.it/showlist/')
    soup = BeautifulSoup(r.text)


    for row in soup.find_all('tr'):
        
        name = ''
        url = ''
        status = ''
        for a in row.find_all('a', href=True):
            url =  str(a['href'])
            name =  str(a.get_text())

        info = url.strip('/').split('/')

        url = "https://eztv.it" + url
        if len(info) == 3:
            show_id = info[1]
            path = info[2]
        else:
            continue

        for font in row.find_all('font'):
            status = font.get_text()

        db.query("INSERT INTO shows (`show_id`, `name`, `url`, `path`, `status`, `update`) VALUES ('%s', '%s', '%s', '%s', '%s', 0) ON DUPLICATE KEY UPDATE status = '%s', url = '%s'" % (show_id, db.escape_string(str(name)), url, path, db.escape_string(status), db.escape_string(status), url))


def update_available_eps(url, show_id):
    db = get_db()
    ep = requests.get(url)
    eps = BeautifulSoup(ep.text)

    for episode in eps.find_all('tr'):
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

def get_tvdb_id(show_id, imdb_id):
    tvdb = requests.get("http://thetvdb.com/api/GetSeriesByRemoteID.php?imdbid="+imdb_id+"&language=en")
    xml = tvdb.text.encode('utf-8')

    parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
    h = fromstring(xml, parser=parser)

    if h is not None:
        s = h.find("Series")
        if s is not None:
            try:
                tvdb_id = s.find("seriesid").text
            except:
                tvdb_id = ''

            try:
                tvdb_baner = s.find("banner").text
            except:
                tvdb_baner = ''

            try:
                first_aired = s.find("FirstAired").text
            except:
                first_aired = ''

            if tvdb_baner != '':
                tvdb_baner = "http://www.thetvdb.com/banners/" + tvdb_baner
                urllib.urlretrieve(tvdb_baner, "static/img/" + show_id + "_banner.jpg")
            
            print tvdb_id, first_aired

            db = get_db()
            db.query("UPDATE shows SET tvdb = '%s', banner = '%s', date = '%s' WHERE show_id = '%s'" % (tvdb_id, tvdb_baner, first_aired, show_id))


            tvdb = requests.get("http://thetvdb.com/api/" + config.get("tvdb", "api_key") + "/series/" + tvdb_id + "/all/en.xml")
            xml = tvdb.text.encode('utf-8')
            a = fromstring(xml, parser=parser)

            if a is not None:
                s = a.find("Series")
                if s is not None:
                    img = s.find("fanart")
                    if img is not None:
                        fanart = "http://www.thetvdb.com/banners/" + img.text
                        urllib.urlretrieve(fanart, "static/img/" + show_id + ".jpg")
                        db.query("UPDATE shows SET img = '%s' WHERE show_id = '%s'" % (fanart, show_id))

                episodes = a.findall("Episode")
                for ep in episodes:
                    try:
                        i = ep.find("id").text
                    except:
                        i = ''

                    try:
                        number = ep.find("EpisodeNumber").text
                    except:
                        number = ''

                    try:
                        season = ep.find("SeasonNumber").text
                    except:
                        season = ''

                    try:
                        first_aired = ep.find("FirstAired").text
                    except:
                        first_aired = ''

                    try:
                        imdb = ep.find("IMDB_ID").text
                    except:
                        imdb = ''

                    try:
                        overview = ep.find("Overview").text.encode('utf-8')
                    except:
                        overview = ''

                    try:
                        ep_name = ep.find("EpisodeName").text.encode('utf-8')
                    except:
                        ep_name = ''

                    try:
                        img = ep.find("filename").text
                        fanart = "http://www.thetvdb.com/banners/" + img
                        urllib.urlretrieve(fanart, "static/img/" + show_id + "_" + season + "_" + number + ".jpg")
                    except:
                        fanart = ''


                    db.query("UPDATE episodes SET img ='%s', tvdb = '%s', imdb = '%s', plot = '%s', name = '%s', `date` = '%s' WHERE number = '%s' AND season = '%s' AND show_id = '%s'" % (fanart, i, imdb, db.escape_string(overview), db.escape_string(ep_name), first_aired, number, season, show_id))
                    print i, season, number, first_aired, imdb, overview, ep_name, img
                    print overview
            



def fetch_show_info(show_id, name, imdb_id):
    if ', The' in name:
        name = 'The ' + ''.join(name.split(', The'))
        # print name
    
    if imdb_id == '':
        r = requests.get("http://www.omdbapi.com/?t=%s&y=&plot=short&r=json" % name)
    else:
        r = requests.get("http://www.omdbapi.com/?i=%s&y=&plot=short&r=json" % imdb_id)

    a = json.loads(r.text)

    db = get_db()

    print a

    try:
        if 'imdbRating' not in a:
            a['imdbRating'] = ""
        elif a['imdbRating'] == 'N/A':
            a['imdbRating'] = ""
        else:
            a['imdbRating'] = db.escape_string(a['imdbRating'])

        if 'Plot' not in a:
            a['Plot'] = ""
        elif a['Plot'] == 'N/A':
            a['Plot'] = ""
        else:
            a['Plot'] = db.escape_string(a['Plot'])

        if 'Poster' not in a:
            a['Poster'] = ""
        elif a['Poster'] == 'N/A':
            a['Poster'] = ""
        else:
            urllib.urlretrieve(a['Poster'], "static/img/" + show_id + ".jpg")
            a['Poster'] = db.escape_string(a['Poster'])

        if 'imdbID' not in a:
            a['imdbID'] = ""

        db.query("UPDATE shows SET rating = '%s', plot = '%s', img = '%s', imdb = '%s' WHERE show_id = %s" % (a['imdbRating'], a['Plot'], a['Poster'], a['imdbID'], show_id))
        return a['imdbRating'], a['Plot'], a['Poster'], a['imdbID']
    except:
        if 'Poster' in a and a['Poster'] != 'N/A':
            urllib.urlretrieve(a['Poster'], "static/img/" + show_id + ".jpg")
        else:
            a['Poster'] = ''
        db.query("UPDATE shows SET imdb = '%s', img = '%s' WHERE show_id = %s" % ( a['imdbID'], a['Poster'], show_id))
        # print "ERROR ERROR ERROR ERROR ERROR"
        return False
    



def check_new_eps_active():
    db = get_db()
    db.query("SELECT * FROM shows WHERE `update` = 1")
    res = db.store_result()
    i = res.fetch_row(how=1)
    while i:
        update_available_eps(i[0]['url'], i[0]['show_id'])
        fetch_show_info(i[0]['show_id'], i[0]['name'], i[0]['imdb'])
        i = res.fetch_row(how=1)

def download_missing():
    db = get_db()
    csrf = requests.get(transmission_server)
    soup = BeautifulSoup(csrf.text)
    session = soup.code.get_text().split(":")[1].strip()

    headers = {'X-Transmission-Session-Id': session}

    db.query("SELECT * FROM episodes e JOIN shows s ON e.show_id = s.show_id  WHERE `update` = 1 GROUP BY s.show_id, season, number HAVING MAX(downloaded) = 0")
    res = db.store_result()
    i = res.fetch_row(how=1)
    
    downloading = ""
    while i:
        downloading += i[0]['name']+ ' - Season ' + str(i[0]['season'])+', Episode '+ str(i[0]['number']) + "\n"
        payload = {
                "method": "torrent-add",
                "arguments": {
                    "paused": False,
                    "filename": i[0]['magnet'],
                    "download-dir": config.get("transmission", "dir") + "/%s/season %s/" % (i[0]['path'].replace("-", " "), i[0]['season'])
                }
            }
        r = requests.post(transmission_server, data=json.dumps(payload), headers=headers)
        if r.status_code == 200:
            db.query("UPDATE episodes SET downloaded = 1 WHERE show_id = %s AND number = %s and season = %s" % (i[0]['show_id'], i[0]['number'], i[0]['season']))

        i = res.fetch_row(how=1)

    if downloading:
        for number in config.get("twilio", "to").split(","):
            twilio.messages.create(
                to=number.strip(), 
                from_=config.get("twilio", "from"),
                body="Now Downloading... \n\n" + downloading,
            )


@app.route("/")
def index():
    db = get_db()
    db.query("SELECT * FROM shows s WHERE `update` = 1 ORDER BY name ASC")
    res = db.store_result()

    updating = []
    i = res.fetch_row(how=1)
    while i:
        updating.append(i[0])
        i = res.fetch_row(how=1)

    db.query("SELECT * FROM shows s WHERE `update` != 1 ORDER BY name ASC")
    res = db.store_result()

    available = []
    i = res.fetch_row(how=1)
    while i:
        available.append(i[0])
        i = res.fetch_row(how=1)

    return render_template('index.html', shows_updating = updating, shows_available = available)


@app.route("/<show_path>")
def get_show(show_path):
    db = get_db()
    db.query("SELECT * FROM shows s WHERE path = '%s'" % show_path)    
    res = db.store_result()
    show = res.fetch_row(how=1)[0]

    db.query("SELECT *, MAX(downloaded) got FROM episodes e JOIN shows s ON e.show_id = s.show_id  WHERE s.path = '%s' AND `update` = 1 GROUP BY s.show_id, season, number" % show_path)    
    res = db.store_result()

    episodes = {}
    i = res.fetch_row(how=1)
    while i:
        i = i[0]
        if "Season " + i['season'] not in episodes:
            episodes["Season " + i['season']] = []

        episodes["Season " + i['season']].append(i)
        i = res.fetch_row(how=1)


    return render_template('show.html', show = show, episodes = episodes)

if __name__ == '__main__':
    if sys.argv[1] == "serve":
        app.run(host="0.0.0.0", debug=config.getboolean("app", "debug"))

    elif sys.argv[1] == "update":
        update_available_shows()
        check_new_eps_active()
        download_missing()

    elif sys.argv[1] == "info":
        db = get_db()
        db.query("SELECT * FROM shows WHERE `update` = 1 ORDER BY name ASC")
        res = db.store_result()

        i = res.fetch_row(how=1)
        while i:
            fetch_show_info(i[0]['show_id'], i[0]['name'], i[0]['imdb'])
            i = res.fetch_row(how=1)
    
    elif sys.argv[1] == "tvdb":
        db = get_db()
        db.query("SELECT * FROM shows WHERE `update` = 1 ORDER BY name ASC")
        res = db.store_result()

        i = res.fetch_row(how=1)
        while i:
            get_tvdb_id(i[0]['show_id'], i[0]['imdb'])
            i = res.fetch_row(how=1)






