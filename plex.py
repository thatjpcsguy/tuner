#!/usr/local/bin/python3

from plexapi.myplex import MyPlexAccount, PlexServer
import sys
import shutil
import os
import filetype
import time

plex_token = "wQKEtGXu_bz3aWCmscSN"
plex_url = "http://127.0.0.1:32400"
movies_directory = '/Volumes/Bertha 2TB/Movies/Clean/'

plex = PlexServer(plex_url, plex_token)
movies = plex.library.section('Movies')
tv = plex.library.section('TV Shows')


if __name__ == '__main__':
    if '--search' in sys.argv:
        for movie in movies.search(sys.argv[2]):
            print(movie.title)
            print(movie.key)
            print(movie.media)
            for media in movie.media:
                print("\tID: %s" % media.id)
                print("\tBitrate: %s" % media.bitrate)
                print("\tContainer: %s" % media.container)
                print("\tVideoResolution: %s" % media.videoResolution)
                print("\tWidth: %s" % media.width)
                print("\tHeight: %s" % media.height)
                for part in media.parts:
                    print("\tFile: %s" % part.file)
                
                print("")
            print('')

    if '--cleanup' in sys.argv:
        
        for movie in movies.search(""):
            # if len(movie.media) > 1: 
            for media in movie.media:
                
                # print(movie.year)
                # print(movie.key)
                # print(movie.media)
                # print("\tID: %s" % media.id)
                # print("\tBitrate: %s" % media.bitrate)
                if media.container:
                    
                    # print("\tWidth: %s" % media.width)
                    # print("\tHeight: %s" % media.height)
                    # print("\tDuration: %s" % media.duration)
                    for part in media.parts:
                        
                        new_filename = "%s%s (%s).%s" % (movies_directory, movie.title, movie.year, media.container)
                        new_filename = new_filename.replace(':', '-')

                        if new_filename != part.file and movie.year is not None:
                            # print(movie.title)
                            # print("\tContainer: %s" % media.container)
                            # print("\tVideoResolution: %s" % media.videoResolution)
                            # print("\tFile: %s" % part.file)
                            # print("\tNew File: %s" % new_filename)

                            try:
                                shutil.move(part.file, new_filename)
                            except:
                                # print('\t!Move Failed!')
                                pass
                            
                            time.sleep(5)
                            # print("Moved")
                            # print("\tSize: %s" % part.size)
                            # print("")


    if '--optimize' in sys.argv:
        plex.library.cleanBundles()
        plex.library.optimize()


    if '--maintenance' in sys.argv:
        movies.analyze()
        movies.emptyTrash()
        movies.update()
        tv.analyze()
        tv.emptyTrash()
        tv.update()


