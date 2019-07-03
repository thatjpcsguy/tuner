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


_host = 'https://thepiratebay.org'
_page = '/top/207'
_host_1337x = 'http://1337x.to'
_page_1337x = '/top-100-eng-movies'

def hash(x):
    return hashlib.sha256(str(x).lower().strip().encode('utf8')).hexdigest()


def exists(h, path='cache'):
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


def list_top100(page=_page):
    # print(page)
    ep = requests.get(_host + page)
    soup = BeautifulSoup(ep.text, "lxml")

    movies = {}

    for row in soup.find_all('tr'):
        for a in row.find_all('a', href=True, class_='detLink'):
            # print(se)
            cells = row.find_all("td", {"align": "right"})
            # print(cells)
            se = cells[0].string if cells else 0
            le = cells[1].string if cells else 0
            href = a.get('href')
            id = href.split('/torrent/')[1].split('/')[0]
            # print id
            # exit()
            name = a.get_text()
            info = PTN.parse(name)
            quality = info['quality'] if 'quality' in info else 'Unknown'
            resolution = info['resolution'] if 'resolution' in info else 'Unknown'
            year = info['year'] if 'year' in info else 'XXXX'
            title = info['title'].strip().rstrip('.').lower()

            magnet = ''

            if title not in movies:
                movies[title] = {}

            movies[title][id] = {
                'hash': hash(title),
                'title': title,
                'id': id,
                'url': href,
                'magnet': False,
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


def list_top_1337x(page=_page_1337x):
    ep = requests.get(_host_1337x + page)
    soup = BeautifulSoup(ep.text, "lxml")

    movies = {}
    for row in soup.find_all('tr'):
        # print('new row:')
        # print(row)
        links = row.find_all('a', href=True)
        # print(links)
        if not links:
            continue
        a = links[1]

        se = row.find_all('td', class_='seeds')[0].get_text()
        le = row.find_all('td', class_='leeches')[0].get_text()
        # print(se, le)

        href = a.get('href')
        id = href.split('/torrent/')[1].split('/')[0]

        name = a.get_text()
        info = PTN.parse(name)
        quality = info['quality'] if 'quality' in info else 'Unknown'
        resolution = info['resolution'] if 'resolution' in info else 'Unknown'
        year = info['year'] if 'year' in info else 'XXXX'
        title = info['title'].strip().rstrip('.')

        magnet = ''

        if title not in movies:
            movies[title] = {}

        movies[title][id] = {
            'hash': hash(title),
            'title': title,
            'id': id,
            'url': href,
            'magnet': False,
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


def download(id, magnet=False):
    transmission_server = 'http://10.1.1.11:9091/ui/rpc'
    
    if not magnet:
        magnet = get_magnet(id)
    
    if exists(id, path='downloads'):
        return True

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
#            "download-dir": "/Volumes/Bertha 2TB/Movies/Downloads/"
            "download-dir": "/Volumes/Movies/Downloads/"
        }
    }
    r = requests.post(transmission_server, data=json.dumps(payload), headers=headers, verify=False)
    if r.status_code == 200:
        save(id, magnet, path='downloads')
        return True
    return False


def get_magnet(id):
    if not exists(id, path='magnets'):    
        ep = requests.get(_host + '/torrent/' + id)
        soup = BeautifulSoup(ep.text, "lxml")
        download = soup.find_all(class_='download')[0]
        return save(id, download.find_all('a')[0].get('href'), path='magnets')
    return load(id, path='magnets')


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
                        magnet = get_magnet(movies[i][j]['id'])
                        # print(movies[i][j])
                        download(h, magnet)
                        # print("download dry run")
                        break

            if not exists(h, path='downloads') and '--decent' in sys.argv:
                for j in movies[i]:
                    if movies[i][j]['decent']:
                        magnet = get_magnet(movies[i][j]['id'])
                        # print(movies[i][j])
                        download(h, magnet)
                        # print("download dry run 720")
                        break


    # --download <id> <name>
    if '--download' in sys.argv:
        id = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else str(id)
        h = hash(name)
        magnet = get_magnet(id)
        # print(magnet)
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
        movies = list_top100(page="/s/?video=on&category=0&page=0&orderby=99&q=%s" % sys.argv[2])
        for i in movies:
            h = hash(i)
            if not exists(h, path='downloads'):
                print('> ' + i)
                for j in movies[i]:
                    print('\t\t%s %s (%s) [%s, %s]' % (
                        movies[i][j]['id'], movies[i][j]['resolution'], movies[i][j]['quality'], movies[i][j]['se'], movies[i][j]['le']))


    if '--lucky' in sys.argv:
        movies = list_top100(page="/s/?video=on&category=0&page=0&orderby=99&q=%s" % sys.argv[2])
        if len(movies) < 1:
            print('no results')
            exit()

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
                exit()


    if '--help' in sys.argv:
        print("""./movies.py
    --search <term>
    --cache <name>
    --list
    --download <id> <name>
    --auto""")

