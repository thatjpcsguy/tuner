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

# account = MyPlexAccount('thatjpcsguy', '12Dinnison')
# account = MyPlexAccount()
# print(account)
# plex = account.resource('Darkblade').connect()
plex = PlexServer(plex_url, plex_token)

movies = plex.library.section('Movies')
tv = plex.library.section('TV Shows')
# print(account._token)



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

            # print(movie.media)
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

                        if new_filename != part.file:
                            print(movie.title)
                            print("\tContainer: %s" % media.container)
                            print("\tVideoResolution: %s" % media.videoResolution)
                            print("\tFile: %s" % part.file)
                            print("\tNew File: %s" % new_filename)

                            try:
                                shutil.move(part.file, new_filename)
                            except:
                                print('\t!Move Failed!')
                            
                            time.sleep(5)
                            # print("Moved")
                            # print("\tSize: %s" % part.size)
                            print("")


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


    if '--fix' in sys.argv:
        print('--fix 3')

        directory = os.fsencode(movies_directory)

        for file in os.listdir(directory):
            filename = os.fsdecode(file)
            if filename.endswith(".None"):
                 

                print(filename)
                old = movies_directory + filename
                new = movies_directory + filename.rstrip('.None') + '_fix.mp4' 

                print('mv '+ old  + ' ' + new)
                try:
                    shutil.move(old, new)
                    print("Moved")
                except:
                    print('Failed to move')
                
                time.sleep(5)
                
