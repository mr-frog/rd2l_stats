'''rd2l fantasy script V 0.1 by linoli ravioli. Call the script with an integer indicating how many days back to go when looking for games as the first argument'''
import requests
import json
import sys
import datetime
import pandas as pd
import os
from PIL import Image, ImageDraw, ImageFont
import shutil

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
OUT = os.path.join(date.strftime("%Y-%m-%d"),'rd2l_fantasy.out')
RAW = os.path.join(date.strftime("%Y-%m-%d"),'rd2l_fantasy.raw')
PIC = os.path.join(date.strftime("%Y-%m-%d"),'rd2l_fantasy.png')
heroStats = 'heroStats.json'
if not os.path.isfile(heroStats):
    h_s = requests.get(opendota_URL+'heroStats').json()
    with open(heroStats, "w") as hs:
        hs.write(json.dumps(h_s))
        
def get_games(league_id, from_date):
    '''get a list of games in last x days in a given league (rd2l s18 = 11202) from stratz API'''
    game_list = []
    api_data = requests.get(stratz_URL+'league/'+str(league_id)+'/matches?take=50')
    if api_data.status_code == 404:
        print("Stratz API not available, try again later.")
        sys.exit()
    l_d = api_data.json()
    for y in l_d:
        game_date = datetime.date.fromtimestamp(y['startDateTime'])
        if game_date == from_date:
            game_list.append(y['id'])
    return game_list

def calc_fscore(kills, deaths, lh, den, gpm, tower_kill, rosh_kill, tf_participation,
                obs_placed, camp_stacked, rune_taken, first_blood, stun_time):
    '''calculate fantasy score for a given player'''
    return round((
    0.3 * kills
    + 3 - 0.3 * deaths
    + 0.003 * lh
    + 0.003 * den
    + 0.002 * gpm
    + tower_kill
    + rosh_kill
    + 0.5 * obs_placed
    + 0.5 * camp_stacked
    + 0.25 * rune_taken
    + 4 * first_blood
    + 0.05 * stun_time
    + 3 * tf_participation
    ), 1)
    
    
def make_raw(game_list, OUT):
    '''populate raw file with match-stats from opendota-API'''
    with open(RAW, "w") as raw_file:
        raw_file.write('[\n')
        for game in game_list:
            print("Parsing Game %s"%game) 
            
            #Request Matchdata
            response = requests.get(opendota_URL+'matches/'+str(game)+'/')
            r = response.json()
            
            # Write raw data for debugging
            raw_file.write(json.dumps(r))
            if game != game_list[-1]:
                raw_file.write(',')
            raw_file.write('\n')
        raw_file.write(']')
    return 
    
def make_db(raw_file, OUT):
    '''populate database file with legible match-stats'''
    # To convert hero_id into hero name
    
    with open(heroStats, "r") as hs:
        hero_dict = json.load(hs)
        hero_data = pd.DataFrame.from_dict(hero_dict)    

    #Prepare DataFrame
    rd2l_data = pd.DataFrame([],columns = ["Full Match", "Start Time", "Account_id", "Player",
                                            "Fantasy Points", "Kills", "Deaths", "Assists",
                                            "Hero Damage", "Hero Healing", "Last Hits",
                                            "Denies", "GPM", "XPM", "Tow", "Tower Damage",
                                            "Ros", "TF","Obs Placed", "Camps Stacked", "Ru",
                                            "FB", "Stuns", "Hero","Game Length", "Total Kills",
                                            "FPPM", "Lane", "Role", "Hero Pic", "LH@10"])
    with open(raw_file, "r") as raw:
        raw_data = json.load(raw)
                                                                                       
    with open(OUT, "w") as out_file:
        for r in raw_data:
            mid_f = 0
            core_f = 0
            sup_f = 0
            for i in r['players']:
                #To identify first blood (for fantasy scoring)    
                fb = i['firstblood_claimed']

                #Calculate Teamfight participation
                team_score = (r['dire_score'], r['radiant_score'])[i['isRadiant']]
                tf_participation = round((i['kills'] + i['assists']) / team_score, 2)
                    
                #Calculate Fantasy Score    
                fscore = calc_fscore(i['kills'], i['deaths'], i['last_hits'], i['denies'],
                                        i['gold_per_min'], i['tower_kills'], i['roshan_kills'],
                                        tf_participation, i['obs_placed'], i['camps_stacked'],
                                        i['rune_pickups'], fb, round(i['stuns'], 2))
                
                #Attempt role detection
                if i['lane'] == 2 and i['benchmarks']['lhten']['raw'] >= 18:
                    role = 2
                    mid_f += 1
                elif i['benchmarks']['lhten']['raw'] >= 18:
                    role = 3
                    core_f += 1
                else:
                    role = 1
                    sup_f += 1

                
                
                #Convert hero_id to Hero Name
                hero_id = i['hero_id']
                index = hero_data.index[hero_data['id'] == hero_id].tolist()
                hero = hero_data.iat[index[0], 2]
                hero_pic = hero_data.iat[index[0], 6]
                
                #Populate DB
                start_date = datetime.date.fromtimestamp(r['start_time']).strftime("%Y-%m-%d")
                player_frame = pd.DataFrame(
                    [(r['match_id'], start_date, i['account_id'],i['personaname'], fscore, i['kills'],
                    i['deaths'], i['assists'],i['hero_damage'],i['hero_healing'],i['last_hits'],
                    i['denies'], i['gold_per_min'], i['xp_per_min'], i['tower_kills'], 
                    i['tower_damage'], i['roshan_kills'], tf_participation, i['obs_placed'],
                    i['camps_stacked'], i['rune_pickups'], fb, i['stuns'], hero, r['duration'], 
                    (r['dire_score']+r['radiant_score']), round(fscore*60/r['duration'],4),
                    i['lane'], role, hero_pic, i['benchmarks']['lhten']['raw'])],
                    columns = ["Full Match", "Start Time", "Account_id", "Player", 
                    "Fantasy Points", "Kills", "Deaths", "Assists", "Hero Damage", 
                    "Hero Healing", "Last Hits", "Denies", "GPM", "XPM", "Tow", 
                    "Tower Damage", "Ros", "TF","Obs Placed", "Camps Stacked", "Ru",
                    "FB", "Stuns", "Hero", "Game Length", "Total Kills", "FPPM",
                    "Lane", "Role", "Hero Pic", "LH@10"])
                rd2l_data = rd2l_data.append(player_frame, ignore_index = True)
            if (mid_f > 2) or (core_f > 4) or (sup_f > 4):
                print("Check %s (Mid: %s, Core: %s, Sup: %s)"%(r['match_id'], mid_f, core_f, sup_f))    
        #Write DB to file        
        rd2l_data.to_csv(OUT, index = False)
        
def makeimage(player_names, point_list, date):
#Generate Fantasy Team Image
    top = 50
    p_top = top + 70
    h_top = p_top + 150
    a = Image.new('RGB', (850,400), color='Grey')
    h1 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'core_0.png')).resize((150,84), resample=1)
    h2 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'core_1.png')).resize((150,84), resample=1)
    h3 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'mid_0.png')).resize((150,84), resample=1)
    h4 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'sup_0.png')).resize((150,84), resample=1)
    h5 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'sup_1.png')).resize((150,84), resample=1)
    p1 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'core_player_0.png')).resize((150,150), resample=1)
    p2 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'core_player_1.png')).resize((150,150), resample=1)
    p3 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'mid_player_0.png')).resize((150,150), resample=1)
    p4 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'sup_player_0.png')).resize((150,150), resample=1)
    p5 = Image.open(os.path.join(date.strftime('%Y-%m-%d'), 'sup_player_1.png')).resize((150,150), resample=1)
    
    a.paste(h1, (50, h_top))
    a.paste(h2, (200, h_top))
    a.paste(h3, (350, h_top))
    a.paste(h4, (500, h_top))
    a.paste(h5, (650, h_top))
    
    a.paste(p1, (50, p_top))
    a.paste(p2, (200, p_top))
    a.paste(p3, (350, p_top))
    a.paste(p4, (500, p_top))
    a.paste(p5, (650, p_top))
    
    draw = ImageDraw.Draw(a)
    size = 30
    fnt = ImageFont.truetype('arial.ttf', size)
    date_string = date.strftime('%a, %d.%m.')
    w, h = draw.textsize("RD2L Fantasy Dream Team - %s"%date_string, font = fnt)
    draw.text(((850-w)/2, 10), "RD2L Fantasy Dream Team - %s"%date_string, font = fnt, fill = 'black')  
    size = 26
    fnt = ImageFont.truetype('arial.ttf', size)    
    w, h = draw.textsize("Core", font = fnt)
    draw.text(((400-w)/2, top), "Core", font = fnt, fill = 'black')
    w, h = draw.textsize("Mid", font = fnt)
    draw.text(((850-w)/2, top), "Mid", font = fnt, fill = 'black')
    w, h = draw.textsize("Suppot", font = fnt)
    draw.text(((1300-w)/2, top), "Support", font = fnt, fill = 'black')
    r = 250
    for name in player_names:
        size = 26
        fnt = ImageFont.truetype('arial.ttf', size)
        w, h = draw.textsize(name, font = fnt)
        while w > 150:
            size -= 1
            fnt = ImageFont.truetype('arial.ttf', size)
            w, h = draw.textsize(name, font = fnt)
        draw.text(((r-w)/2, top+35), name, font = fnt)
        r+= 300
    r = 250
    for points in point_list:
        size = 26
        fnt = ImageFont.truetype('arial.ttf', size)
        w, h = draw.textsize(str(points), font = fnt)
        draw.text(((r-w)/2, h_top + 89), str(points), font = fnt)
        r+= 300
    return a      


#Only make new DB if not existant yet
if not os.path.isdir(date.strftime("%Y-%m-%d")):
    os.mkdir(os.path.join(date.strftime("%Y-%m-%d")))
    
if not os.path.isfile(RAW):
    print("Fetching List of Games on %s."%date.strftime("%Y-%m-%d"))
    game_list = get_games(11202, date)
    print("Found %s games."%len(game_list))
    if len(game_list) == 0:
        sys.exit()
    print("Populating Database")
    make_raw(game_list, OUT)

make_db(RAW, OUT)

#Print stats    
print("\nrd2l Stats:")
rd2l_data = pd.read_csv(OUT)

col_list = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 18, 19, 26] #Columns to print

for col in col_list:
    player = rd2l_data.iat[rd2l_data[rd2l_data.columns[col]].idxmax(), 3]
    points = rd2l_data.iat[rd2l_data[rd2l_data.columns[col]].idxmax(), col]
    hero = rd2l_data.iat[rd2l_data[rd2l_data.columns[col]].idxmax(), 23]
    game = rd2l_data.iat[rd2l_data[rd2l_data.columns[col]].idxmax(), 0]
    category = rd2l_data.columns[col]
    print("**Most %s** - %s on %s with %s (<https://www.opendota.com/matches/%s>)"%(category, player, hero, points, game))

top_heroes = rd2l_data['Hero'].value_counts()
print("**Top 3 Heroes Picked** - %s (%s), %s (%s), %s (%s)"%(top_heroes.index[0], top_heroes.iat[0], top_heroes.index[1], top_heroes.iat[1], top_heroes.index[2], top_heroes.iat[2]))
#Longest Game
game = rd2l_data.iat[rd2l_data["Game Length"].idxmax(), 0]
time = rd2l_data.iat[rd2l_data["Game Length"].idxmax(), 24]
print("**Longest Game** - %s (<https://www.opendota.com/matches/%s>)"%(datetime.timedelta(seconds=int(time)),game))
#Shortest Game
game = rd2l_data.iat[rd2l_data["Game Length"].idxmin(), 0]
time = rd2l_data.iat[rd2l_data["Game Length"].idxmin(), 24]
print("**Shortest Game** - %s (<https://www.opendota.com/matches/%s>)"%(datetime.timedelta(seconds=int(time)), game))
#Most Kills
game = rd2l_data.iat[rd2l_data["Total Kills"].idxmax(), 0]
kills = rd2l_data.iat[rd2l_data["Total Kills"].idxmax(), 25]
print("**Most Kills** - %s (<https://www.opendota.com/matches/%s>)"%(kills, game))
#Least Kills
game = rd2l_data.iat[rd2l_data["Total Kills"].idxmin(), 0]
kills = rd2l_data.iat[rd2l_data["Total Kills"].idxmin(), 25]
print("**Least Kills** - %s (<https://www.opendota.com/matches/%s>)"%(kills, game))
#Fantasy Dream Team
print("**RD2L Fantasy Dream Team**")
player_names=[]
point_list=[]

#Core
print("**Core**")
sort_data = rd2l_data[rd2l_data['Role']==3]
sort_data = sort_data.sort_values(by = 'Fantasy Points', ascending = False)
for i in [0, 1]:
    player = sort_data.iat[i, 3]
    points = sort_data.iat[i, 4]
    hero = sort_data.iat[i, 23]
    game = sort_data.iat[i, 0]
    hero_pic = sort_data.iat[i, 29]
    #Hero Pic
    hero_pic = sort_data.iat[i, 29]
    s_hp = os.path.join(date_string,'core_'+str(i)+'.png')
    if not os.path.isfile(s_hp):
        url = 'https://api.opendota.com'+hero_pic
        pic = requests.get(url, stream = True)
        if pic.status_code == 200:
            with open(s_hp, "wb") as f:
                pic.raw.decode_content = True
                shutil.copyfileobj(pic.raw, f)
    #Player Pic
    player_id = sort_data.iat[i,2]
    s_pp = os.path.join(date_string,'core_player_'+str(i)+'.png')
    if not os.path.isfile(s_pp):
        player_url = requests.get(opendota_URL+'players/'+str(player_id)).json()['profile']['avatarfull']
        pic = requests.get(player_url, stream = True)
        if pic.status_code == 200:
            with open(s_pp, "wb") as f:
                pic.raw.decode_content = True
                shutil.copyfileobj(pic.raw, f)  
                
    print("\t%s on %s with %s (<https://www.opendota.com/matches/%s>)"%(player, hero, points, game))
    
    player_names.append(player)
    point_list.append(points)
    
print("**Mid**")
sort_data = rd2l_data[rd2l_data['Role']==2]
sort_data = sort_data.sort_values(by = 'Fantasy Points', ascending = False)
for i in [0]:
    player = sort_data.iat[i, 3]
    points = sort_data.iat[i, 4]
    hero = sort_data.iat[i, 23]
    game = sort_data.iat[i, 0]
    #Hero Pic
    hero_pic = sort_data.iat[i, 29]
    s_hp = os.path.join(date_string,'mid_'+str(i)+'.png')
    if not os.path.isfile(s_hp):
        url = 'https://api.opendota.com'+hero_pic
        pic = requests.get(url, stream = True)
        if pic.status_code == 200:
            with open(s_hp, "wb") as f:
                pic.raw.decode_content = True
                shutil.copyfileobj(pic.raw, f)
    #Player Pic
    player_id = sort_data.iat[i,2]
    s_pp = os.path.join(date_string,'mid_player_'+str(i)+'.png')
    if not os.path.isfile(s_pp):
        player_url = requests.get(opendota_URL+'players/'+str(player_id)).json()['profile']['avatarfull']
        pic = requests.get(player_url, stream = True)
        if pic.status_code == 200:
            with open(s_pp, "wb") as f:
                pic.raw.decode_content = True
                shutil.copyfileobj(pic.raw, f)  
    print("\t%s on %s with %s (<https://www.opendota.com/matches/%s>)"%(player, hero, points, game))
    player_names.append(player)
    point_list.append(points)
    
print("**Support**")
sort_data = rd2l_data[rd2l_data['Role']==1]
sort_data = sort_data.sort_values(by = 'Fantasy Points', ascending = False)

for i in [0, 1]:
    player = sort_data.iat[i, 3]
    points = sort_data.iat[i, 4]
    hero = sort_data.iat[i, 23]
    game = sort_data.iat[i, 0]
    #Hero Pic
    hero_pic = sort_data.iat[i, 29]
    s_hp = os.path.join(date_string,'sup_'+str(i)+'.png')
    if not os.path.isfile(s_hp):
        url = 'https://api.opendota.com'+hero_pic
        pic = requests.get(url, stream = True)
        if pic.status_code == 200:
            with open(s_hp, "wb") as f:
                pic.raw.decode_content = True
                shutil.copyfileobj(pic.raw, f)
    #Player Pic
    player_id = sort_data.iat[i,2]
    s_pp = os.path.join(date_string,'sup_player_'+str(i)+'.png')
    if not os.path.isfile(s_pp):
        player_url = requests.get(opendota_URL+'players/'+str(player_id)).json()['profile']['avatarfull']
        pic = requests.get(player_url, stream = True)
        if pic.status_code == 200:
            with open(s_pp, "wb") as f:
                pic.raw.decode_content = True
                shutil.copyfileobj(pic.raw, f)  
            
    print("\t%s on %s with %s (<https://www.opendota.com/matches/%s>)"%(player, hero, points, game))
    player_names.append(player)
    point_list.append(points)

#Image
image = makeimage(player_names, point_list, date)
image.save(PIC)