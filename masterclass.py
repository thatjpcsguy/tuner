#!/usr/local/bin/python3

import requests
import os.path
import pickle
import json
import multiprocessing
import hashlib
import os
import sys
import configparser

from bs4 import BeautifulSoup
import PTN


_host = 'https://apibay.org'
_page = '/search.php?q=top100:207'
_host_1337x = 'http://1337x.to'
_page_1337x = '/top-100-eng-movies'

def hash(x):
    return hashlib.sha256(str(x).lower().strip().encode('utf8')).hexdigest()


def exists(h, path='cache'):
    if '--nocache' in sys.argv:
        return False
    if os.path.isfile(path + '/%s.pickle' % h):
        return True
    return False

def save(h, x, path='cache'):
    with open(path + '/%s.pickle' % h, 'wb') as f:
        pickle.dump(x, f)
        return x


def load(h, path='cache'):
    with open(path + '/%s.pickle' % h, 'rb') as f:
        return pickle.load(f)


def list_top100(url='/precompiled/data_top100_207.json'):
    url = _host + url

    data = requests.get(url).json()
    movies = {}

    for movie in data:
        se = movie['seeders']
        le = movie['leechers']
        id = movie['id']
        name = movie['name']
        info = PTN.parse(name)
        quality = info['quality'] if 'quality' in info else 'Unknown'
        resolution = info['resolution'] if 'resolution' in info else 'Unknown'
        year = info['year'] if 'year' in info else 'XXXX'
        title = info['title'].strip().rstrip('.').lower()
        lookup_title = '%s %s' % (title, year)
        ih = movie['info_hash']

        magnet = 'magnet:?xt=urn:btih:' + ih + print_trackers()

        if lookup_title not in movies:
            movies[lookup_title] = {}

        movies[lookup_title][id] = {
            'hash': hash(lookup_title),
            'title': title,
            'id': id,
            'magnet': magnet,
            'le': le,
            'se': se,
            'year': year, 
            'raw': name, 
            'quality': quality, 
            'resolution': resolution,
            'parse': info,
            'good': (quality.lower() in ('brrip', 'bluray', 'webrip', 'web-dl')) and resolution == '1080p',
            'decent': (quality.lower() in ('brrip', 'bluray', 'webrip', 'web-dl')) and resolution == '720p'
        }

    return movies


def download_deluge(magnet, directory):
    deluge_server = 'http://10.1.1.11:8112/json'

    cookies = None
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}

    payload = {"id": 1, "method": "auth.login", "params": ["deluge"]}
    response = requests.post(deluge_server, data=json.dumps(
        payload), headers=headers, cookies=cookies)

    auth = response.json()
    cookies = response.cookies

    payload = json.dumps({"id": 2, "method": "webapi.add_torrent", "params": [magnet, {"move_completed_path": directory, "move_completed": True, "download_path": "/Volumes/Orange/Incomplete"}]})

    response = requests.post(deluge_server, data=payload, headers=headers, cookies=cookies)

    return response.status_code


def download_transmission(magnet, directory):
    transmission_server = 'http://10.1.1.12:9092/transmission/rpc'
    csrf = requests.get(transmission_server)
    soup = BeautifulSoup(csrf.text, "lxml")
    # print soup.code
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

def strip_junk(s):
    s = s.strip()
    bad_chars = "';:!*()[].,"

    for i in bad_chars:
        s = s.replace(i, '')

    return s


def download(id, magnet=False):
    directory = "/Volumes/Blue/Masterclass/"
    
    if not magnet:
        magnet = get_magnet(id)
    
    if exists(id, path='downloads'):
        return True

    t = download_transmission(magnet, directory)
    # t = 200
    # t = download_deluge(magnet, directory)
   
    # print(t, d)
    if t == 200:
        save(id, magnet, path='downloads')
        return True
    return False


def get_magnet(id):
    if not exists(id, path='magnets'):    
        r = requests.get(_host + '/t.php?id=' + id)

        data = r.json()
        ih = data['info_hash']

        magnet = 'magnet:?xt=urn:btih:' + ih + print_trackers()

        return save(id, magnet, path='magnets')
    return load(id, path='magnets')



def print_trackers():
    tr = '&tr=' + 'udp://tracker.coppersurfer.tk:6969/announce'
    tr += '&tr=' + 'udp://9.rarbg.to:2920/announce'
    tr += '&tr=' + 'udp://tracker.opentrackr.org:1337'
    tr += '&tr=' + 'udp://tracker.internetwarriors.net:1337/announce'
    tr += '&tr=' + 'udp://tracker.leechers-paradise.org:6969/announce'
    tr += '&tr=' + 'udp://tracker.coppersurfer.tk:6969/announce'
    tr += '&tr=' + 'udp://tracker.pirateparty.gr:6969/announce'
    tr += '&tr=' + 'udp://tracker.cyberia.is:6969/announce'
    return tr




def lucky(search):
    search = strip_junk(search)
    h = hash(search)
    if exists(h, path='downloads'):
        return

    movies = list_top100(
        page="/s/?video=on&category=0&page=0&orderby=99&q=%s" % search)

    if len(movies) < 1:
        print('no results')
        return

    t = ''
    for i in movies:
        t = i
        break

    first = movies[t]
    for j in first:
        if first[j]['good']:
            print(first[j]['hash'])
            print('%s %s %s (%s) [%s, %s]' % (
                first[j]['title'], first[j]['id'], first[j]['resolution'], first[j]['quality'], first[j]['se'], first[j]['le']))
            magnet = get_magnet(first[j]['id'])
            download(first[j]['hash'], magnet)
            return

if __name__ == '__main__':
    if '--list1337x' in sys.argv:
        movies = list_top_1337x()
        for i in movies:
            h = hash(i)
            if not exists(h, path='downloads'):
                print('> ' + i)
                for j in movies[i]:
                    print('\t\t%s %s (%s) [%s, %s]' % (
                        movies[i][j]['id'], movies[i][j]['resolution'], movies[i][j]['quality'], movies[i][j]['se'], movies[i][j]['le']))


    if '--list' in sys.argv:
        movies = list_top100()
        for i in movies:
            h = hash(i)
            if not exists(h, path='downloads'):
                print('> ' + i)
                for j in movies[i]:
                    print('\t\t%s %s (%s) [%s, %s]' % (
                        movies[i][j]['id'], movies[i][j]['resolution'], movies[i][j]['quality'], movies[i][j]['se'], movies[i][j]['le']))


    if '--auto' in sys.argv:
        movies = list_top100()
        for i in movies:
            h = hash(i)
            if not exists(h, path='downloads'):
                for j in movies[i]:
                    if movies[i][j]['good']:
                        download(h, movies[i][j]['magnet'])
                        break

            if not exists(h, path='downloads') and '--decent' in sys.argv:
                for j in movies[i]:
                    if movies[i][j]['decent']:
                        download(h, movies[i][j]['magnet'])
                        break


    # --download <id> <name>
    if '--download' in sys.argv or '--dl' in sys.argv:
        id = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else str(id)
        h = hash(name)
        magnet = get_magnet(id)
        # print(magnet)
        download(h, magnet)

    if '--magnet' in sys.argv:
        magnet = sys.argv[2]
        h = hash(magnet)
        download(h, magnet)

    # --cache <name>
    if '--cache' in sys.argv:
        name = sys.argv[2]
        h = hash(name)
        if not exists(h, path='downloads'):
            print('saving')
            save(h, '', path='downloads')
        else:
            print('exists')


    if '--search' in sys.argv:
        movies = list_top100(url="/q.php?cat=207&q=%s" % sys.argv[2])
        for i in movies:
            h = hash(i)
            if not exists(h, path='downloads'):
                print('> ' + i)
                for j in movies[i]:
                    print('\t\t%s %s (%s) [%s, %s]' % (
                        movies[i][j]['id'], movies[i][j]['resolution'], movies[i][j]['quality'], movies[i][j]['se'], movies[i][j]['le']))

    if '--file' in sys.argv:
        for movie in open(sys.argv[2]):
            print(movie)
            lucky(movie)

    if '--lucky' in sys.argv:
        lucky(sys.argv[2])


    if '--help' in sys.argv:
        print("""./movies.py
    --search <term>
    --cache <name>
    --list
    --download <id> <name>
    --auto""")


