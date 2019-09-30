'''rd2l fantasy script V 0.1 by linoli ravioli. Call the script with an integer indicating how many days back to go when looking for games as the first argument'''
import fantasy_utils as fu
import datetime
import os
import sys
from PIL import Image
import shutil
import pandas as pd
import requests

if __name__ == '__main__':
    # Make Subdirectories
    if not os.path.isdir('Data'):
        os.mkdir('Data')
    if not os.path.isdir('Output'):
        os.mkdir('Output') 
        
    #Check if days_back is given, set date after which to look for games
    try: 
        sys.argv[1]
    except:
        print("Please specify an integer as the first argument indicating how many days back to look for games.")
        sys.exit()
    days_back = int(sys.argv[1])    
    date = datetime.date.today() + datetime.timedelta(days = -days_back)
    date_string = date.strftime("%Y-%m-%d")

    stratz_URL = 'http://api.stratz.com/api/v1/'
    opendota_URL = 'http://api.opendota.com/api/'
    
    RAW = os.path.join('Output', date_string, 'rd2l_fantasy.raw')
    DAT = os.path.join('Output', date_string, 'rd2l_fantasy.dat')    
    PIC = os.path.join('Output', date_string, 'rd2l_fantasy.png')
    
      
    #Only make new DB if not existant yet
    folder = os.path.join('Output', date_string)
    if not os.path.isdir(folder):
        os.mkdir(folder)
        
    if not os.path.isfile(RAW):
        print("Fetching List of Games on %s."%date_string)
        game_list = fu.get_games(11202, date, 50)
        print("Found %s games."%len(game_list))
        if len(game_list) == 0:
            sys.exit()
        print("Populating Database")
        fu.make_raw(game_list, RAW)
    fu.make_db(RAW, DAT)

    #Print stats    
    print("\nrd2l Stats:")
    rd2l_data = pd.read_csv(DAT)
    rd2l_data['Vision Provided per Minute of Gametime'] = rd2l_data['Total Obs Duration']/(rd2l_data['Game Length']/60)
    rd2l_data['Avg Obs Duration'] = rd2l_data['Total Obs Duration']/rd2l_data['Obs Placed']
    col_list = [36] #Columns to print
    for col in col_list:
        player = rd2l_data.iat[rd2l_data[rd2l_data.columns[col]].idxmax(), 2]
        points = round(rd2l_data.iat[rd2l_data[rd2l_data.columns[col]].idxmax(), col], 2)
        hero = rd2l_data.iat[rd2l_data[rd2l_data.columns[col]].idxmax(), 3]
        game = rd2l_data.iat[rd2l_data[rd2l_data.columns[col]].idxmax(), 0]
        category = rd2l_data.columns[col]
        print("**Most %s** - %s on %s with %s (<https://www.opendota.com/matches/%s>)"%(category, player, hero, points, game))
    obs_data = rd2l_data[rd2l_data['Obs Placed'] > 4].reset_index()
    player = obs_data.iat[obs_data[obs_data.columns[38]].idxmax(), 3]
    points = obs_data.iat[obs_data[obs_data.columns[38]].idxmax(), 38]
    hero = obs_data.iat[obs_data[obs_data.columns[38]].idxmax(), 4]
    game = obs_data.iat[obs_data[obs_data.columns[38]].idxmax(), 1]
    print("**Highest average Obs Duration** - %s on %s with %s (<https://www.opendota.com/matches/%s>)"%(player, hero, points, game))    

    # top_heroes = rd2l_data['Hero'].value_counts()
    # print("**Top 3 Heroes Picked** - %s (%s), %s (%s), %s (%s)"%(top_heroes.index[0], top_heroes.iat[0], top_heroes.index[1], top_heroes.iat[1], top_heroes.index[2], top_heroes.iat[2]))
    # #Longest Game
    # game = rd2l_data.iat[rd2l_data["Game Length"].idxmax(), 0]
    # time = rd2l_data.iat[rd2l_data["Game Length"].idxmax(), 24]
    # print("**Longest Game** - %s (<https://www.opendota.com/matches/%s>)"%(datetime.timedelta(seconds=int(time)),game))
    # #Shortest Game
    # game = rd2l_data.iat[rd2l_data["Game Length"].idxmin(), 0]
    # time = rd2l_data.iat[rd2l_data["Game Length"].idxmin(), 24]
    # print("**Shortest Game** - %s (<https://www.opendota.com/matches/%s>)"%(datetime.timedelta(seconds=int(time)), game))
    # #Most Kills
    # game = rd2l_data.iat[rd2l_data["Total Kills"].idxmax(), 0]
    # kills = rd2l_data.iat[rd2l_data["Total Kills"].idxmax(), 25]
    # print("**Most Kills** - %s (<https://www.opendota.com/matches/%s>)"%(kills, game))
    # #Least Kills
    # game = rd2l_data.iat[rd2l_data["Total Kills"].idxmin(), 0]
    # kills = rd2l_data.iat[rd2l_data["Total Kills"].idxmin(), 25]
    # print("**Least Kills** - %s (<https://www.opendota.com/matches/%s>)"%(kills, game))
    #Fantasy Dream Team
    print("**RD2L Fantasy Dream Team**")
    player_names=[]
    point_list=[]

    for i in (1,2,3,4,5):
        sort_data = rd2l_data[rd2l_data['Role']==i]
        sort_data = sort_data.sort_values(by = 'Fantasy Points', ascending = False)
        player = sort_data.iat[0, 2]
        points = round(sort_data.iat[0, 34], 4)
        hero = sort_data.iat[0, 3]
        game = sort_data.iat[0, 0]
        hero_pic = sort_data.iat[0, 4]
        #Hero Pic
        s_hp = os.path.join('Output', date_string, str(i)+'.png')
        if not os.path.isfile(s_hp):
            url = 'https://api.opendota.com'+hero_pic
            pic = requests.get(url, stream = True)
            if pic.status_code == 200:
                with open(s_hp, "wb") as f:
                    pic.raw.decode_content = True
                    shutil.copyfileobj(pic.raw, f)
        #Player Pic
        player_id = sort_data.iat[0, 1]
        s_pp = os.path.join('Output', date_string, str(i)+'_player.png')
        if not os.path.isfile(s_pp):
            player_url = requests.get(opendota_URL+'players/'+str(player_id)).json()['profile']['avatarfull']
            pic = requests.get(player_url, stream = True)
            if pic.status_code == 200:
                with open(s_pp, "wb") as f:
                    pic.raw.decode_content = True
                    shutil.copyfileobj(pic.raw, f)
                    
        print("\tPos %s: %s on %s with %s (<https://www.opendota.com/matches/%s>)"%(i, player, hero, points, game))
        
        player_names.append(player)
        point_list.append(points)
    

    #Image
    image = fu.makeimage(os.path.join('Output', date_string), player_names, point_list, date)
    image.save(PIC)