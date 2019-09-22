import requests
import json
import sys
import datetime
import pandas as pd
import os
from PIL import Image, ImageDraw, ImageFont
import time
from io import StringIO
from joblib import dump, load
stratz_URL = 'http://api.stratz.com/api/v1/'
opendota_URL = 'http://api.opendota.com/api/'

def get_herostats():
    '''get heroStats.json from opendota for hero names/pics'''
    
    heroStats = 'heroStats.json'
    if not os.path.isfile(heroStats):
        h_s = requests.get(opendota_URL+'heroStats').json()
        with open(heroStats, "w") as hs:
            hs.write(json.dumps(h_s))
            
            
            
def get_games(league_id, from_date, take):
    '''get a list of games in last x days in a given league (rd2l s18 = 11202) from stratz API'''
    game_list = []
    api_data = requests.get(stratz_URL+'league/'+str(league_id)+'/matches?take='+str(take))
    if api_data.status_code == 404:
        print("Stratz API not available, try again later.")
        sys.exit()
    l_d = api_data.json()
    for y in l_d:
        game_date = datetime.date.fromtimestamp(y['startDateTime'])
        if from_date == 0:
            game_list.append(y['id'])
        elif game_date == from_date:
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
    
   
   
def make_raw(game_list, RAW):
    '''populate raw file with match-stats from opendota-API'''
    
    with open(RAW, "w") as raw_file:
        raw_file.write('[\n')
        i = 0
        for game in game_list:
            print("[%s] Parsing Game %s"%(i+1, game)) 
            
            #Request Matchdata
            response = requests.get(opendota_URL+'matches/'+str(game)+'/')
            r = response.json()
            
            # Write raw data for debugging
            raw_file.write(json.dumps(r))
            if game != game_list[-1]:
                raw_file.write(',')
            raw_file.write('\n')
            i += 1
            if i == 60:
                print('Opendota Ratelimit reached, waiting 60s.')
                for i in range(61):
                    sys.stdout.write('\r'+str(i)+' ')
                    sys.stdout.flush()
                    time.sleep(1)
                print('\n')
                i = 0
        raw_file.write(']')
    return 
    
    
    
def make_db(raw_file, OUT, type = 'Ama', pos = 'NA'):
    '''populate database file with legible match-stats'''
    
    # To convert hero_id into hero name
    heroStats = 'heroStats.json'
    if not os.path.isfile(heroStats):
        get_herostats()
    with open(heroStats, "r") as hs:
        hero_dict = json.load(hs)
        hero_data = pd.DataFrame.from_dict(hero_dict)    

    #Prepare DataFrame
    rd2l_data = pd.DataFrame([],columns = ["Full Match", "Start Time", "Account_id", "Player",
                                            "Fantasy Points", "Kills", "Deaths", "Assists",
                                            "Hero Damage", "Hero Healing", "Last Hits",
                                            "Denies", "GPM", "XPM", "Tow", "Tower Damage",
                                            "Ros", "TF", "Obs Placed", "Camps Stacked", "Ru",
                                            "FB", "Stuns", "Hero", "Game Length", "Total Kills",
                                            "FPPM", "Lane", "Hero Pic", "LH@10", "Level", "Sent Placed",
                                            "Obs Killed", "Sent Killed", "Lane Eff", "Lane Role", "Role"])
    with open(raw_file, "r") as raw:
        raw_data = json.load(raw)
                                                                                       
    with open(OUT, "w") as out_file:
        for r in raw_data:
            role_score = 0
            gamers=[]
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
                


                
                
                #Convert hero_id to Hero Name
                hero_id = i['hero_id']
                index = hero_data.index[hero_data['id'] == hero_id].tolist()
                hero = hero_data.iat[index[0], 2]
                hero_pic = hero_data.iat[index[0], 6]
                
                #Populate DB
                name = i['personaname']
                if type == 'Pro':
                    name = ''.join(i for i in i['name'] if ord(i)<128)
                    role_db = pos[pos['Player'] == name]
                    if len(role_db['Position']) > 0:
                        role = role_db.iat[0, 1]
                    else:
                        role = input("%s"%name)
                        new_row = pd.DataFrame([(name, role)], columns = ["Player", "Position"])
                        print(new_row)
                        pos = pos.append(new_row, ignore_index = True)
                        print(pos)
                    
                role = 0
                start_date = datetime.date.fromtimestamp(r['start_time']).strftime("%Y-%m-%d")
                player_frame = pd.DataFrame(
                    [(r['match_id'], start_date, i['account_id'], name, fscore, i['kills'],
                    i['deaths'], i['assists'],i['hero_damage'],i['hero_healing'],i['last_hits'],
                    i['denies'], i['gold_per_min'], i['xp_per_min'], i['tower_kills'], 
                    i['tower_damage'], i['roshan_kills'], tf_participation, i['obs_placed'],
                    i['camps_stacked'], i['rune_pickups'], fb, i['stuns'], hero, r['duration'], 
                    (r['dire_score']+r['radiant_score']), round(fscore*60/r['duration'],4),
                    i['lane'], hero_pic, i['benchmarks']['lhten']['raw'], i['level'],
                    i['sen_placed'], i['observer_kills'], i['sentry_kills'], i['lane_efficiency'], i['lane_role'], role)],
                    columns = ["Full Match", "Start Time", "Account_id", "Player", 
                    "Fantasy Points", "Kills", "Deaths", "Assists", "Hero Damage", 
                    "Hero Healing", "Last Hits", "Denies", "GPM", "XPM", "Tow", 
                    "Tower Damage", "Ros", "TF","Obs Placed", "Camps Stacked", "Ru",
                    "FB", "Stuns", "Hero", "Game Length", "Total Kills", "FPPM",
                    "Lane", "Hero Pic", "LH@10", "Level",
                    "Sent Placed", "Obs Killed", "Sent Killed", "Lane Eff", "Lane Role", "Role"])
                    
                    
                #Attempt role detection
                player_frame.to_csv('temp.csv', index = False)
                role = int(get_roles('role_model.joblib', 'temp.csv'))
                if i['lane_role'] == 2 and role < 4:
                    role = 2
                role_score += role
                player_frame["Role"] = role
                rd2l_data = rd2l_data.append(player_frame, ignore_index = True)
                os.remove('temp.csv')
                gamers.append([name, role])
            if (role_score != 30):
                print("Check %s"%r['match_id'])
                gamerframe = pd.DataFrame(gamers, columns = ["Name", "Role"])
                print(gamerframe)
        #Write DB to file        
        rd2l_data.to_csv(OUT, index = False)
        if type == 'Pro':
            pos.to_csv('pos_cor.dat', index = False)
        
        
        
def makeimage(folder, player_names, point_list, date):
    '''generate a fantasy dream team image'''
    #Generate Fantasy Team Image
    top = 50
    p_top = top + 72
    h_top = p_top + 162
    a = Image.open('fantasy_template.png').resize((1374, 459), resample = 1)
    hero_size = (150, 80)
    player_size = (150, 150)
    h1 = Image.open(os.path.join(folder, '1.png')).resize(hero_size, resample = 1)
    h2 = Image.open(os.path.join(folder, '2.png')).resize(hero_size, resample = 1)
    h3 = Image.open(os.path.join(folder, '3.png')).resize(hero_size, resample = 1)
    h4 = Image.open(os.path.join(folder, '4.png')).resize(hero_size, resample = 1)
    h5 = Image.open(os.path.join(folder, '5.png')).resize(hero_size, resample = 1)
    p1 = Image.open(os.path.join(folder, '1_player.png')).resize(player_size, resample = 1)
    p2 = Image.open(os.path.join(folder, '2_player.png')).resize(player_size, resample = 1)
    p3 = Image.open(os.path.join(folder, '3_player.png')).resize(player_size, resample = 1)
    p4 = Image.open(os.path.join(folder, '4_player.png')).resize(player_size, resample = 1)
    p5 = Image.open(os.path.join(folder, '5_player.png')).resize(player_size, resample = 1)
    b = Image.new('RGB', (154,154), 'silver')
    

    
    draw = ImageDraw.Draw(a)
    size = 26
    fnt = ImageFont.truetype('arial.ttf', size)
    day = date.strftime('%a').upper()
    date_string = 'CET-' + day + ' - ' + date.strftime('%d.%m.')
    w, h = draw.textsize("RD2L Team of the Week", font = fnt)
    draw.text(((1360-w)/2, 5), "RD2L Team of the Week", font = fnt, fill = 'white')
    draw.text((30, 8), "%s"%date_string, font = fnt, fill = 'white')      
    size = 26
    fnt = ImageFont.truetype('arial.ttf', size)    

    r = [50+207+50, 307+207+307, 563+207+563, 873+207+873, 1119+207+1119]
    
    a.paste(b, (int((r[0]-154)/2), p_top-2))
    a.paste(b, (int((r[1]-154)/2), p_top-2))
    a.paste(b, (int((r[2]-154)/2), p_top-2))
    a.paste(b, (int((r[3]-154)/2), p_top-2))
    a.paste(b, (int((r[4]-154)/2), p_top-2))
    
    a.paste(h1, (int((r[0]-150)/2), h_top))    
    a.paste(h2, (int((r[1]-150)/2), h_top))
    a.paste(h3, (int((r[2]-150)/2), h_top))
    a.paste(h4, (int((r[3]-150)/2), h_top))
    a.paste(h5, (int((r[4]-150)/2), h_top))
    
    a.paste(p1, (int((r[0]-150)/2), p_top))
    a.paste(p2, (int((r[1]-150)/2), p_top))
    a.paste(p3, (int((r[2]-150)/2), p_top))
    a.paste(p4, (int((r[3]-150)/2), p_top))
    a.paste(p5, (int((r[4]-150)/2), p_top))
    i = 0
    for name in player_names:
        size = 20
        fnt = ImageFont.truetype('arial.ttf', size)
        w, h = draw.textsize(name, font = fnt)
        while w > 150:
            size -= 1
            fnt = ImageFont.truetype('arial.ttf', size)
            w, h = draw.textsize(name, font = fnt)
        draw.text(((r[i]-w)/2, (top+164-h)/2), name, font = fnt, fill = 'white')
        i += 1
    i = 0
    
    for points in point_list:
        size = 20
        fnt = ImageFont.truetype('arial.ttf', size)
        w, h = draw.textsize(str(points), font = fnt)
        draw.text(((r[i]-w)/2, h_top + 112), str(points), font = fnt)
        i += 1
    return a   

def get_roles(model, data):
    cols = (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 24, 25, 26, 27, 29, 30, 31, 32, 33, 34, 35, 36)
    LR = load(model)
    rd2l_set = pd.read_csv(data, usecols=cols)
    #rd2l_set = rd2l_set[rd2l_set['Role']!=2]
    rd2l_X = rd2l_set.values[:, :len(cols)-1]
    rd2l_Y = rd2l_set.values[:, len(cols)-1]
    rd2l_predictions = LR.predict(rd2l_X)
    return rd2l_predictions    