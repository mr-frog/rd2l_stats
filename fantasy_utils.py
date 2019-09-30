import requests
import json
import sys
import datetime
import pandas as pd
import os
from PIL import Image, ImageDraw, ImageFont
import time
import numpy as np
from joblib import dump, load
stratz_URL = 'http://api.stratz.com/api/v1/'
opendota_URL = 'http://api.opendota.com/api/'

def get_herostats(heroStats):
    '''get heroStats.json from opendota for hero names/pics'''
    
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
    print("Found %s games."%len(game_list))
    return game_list



def calc_fscore(player, game):
    '''calculate fantasy score for a given player'''
    #Calculate Teamfight participation
    team_score = (game['dire_score'], game['radiant_score'])[player['isRadiant']]
    tf_participation = round((player['kills'] + player['assists']) / team_score, 2)
    
    return round((
    0.3 * player['kills']
    + 3 - 0.3 * player['deaths']
    + 0.003 * player['last_hits']
    + 0.003 * player['denies']
    + 0.002 * player['gold_per_min']
    + player['tower_kills']
    + player['roshan_kills']
    + 0.5 * player['obs_placed']
    + 0.5 * player['camps_stacked']
    + 0.25 * player['rune_pickups']
    + 4 * player['firstblood_claimed']
    + 0.05 * player['stuns']
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
    
def prune_data(player, game, hero_data, obs_frame, sen_frame):

    #Calculate Fantasy Score (Valve)
    fscore = calc_fscore(player, game)
    
    #Calculate Impact (Linail)
    impact = calc_impact(player, game)
    
    #Convert hero_id to Hero Name + Hero Pic
    hero_id = player['hero_id']
    index = hero_data.index[hero_data['id'] == hero_id].tolist()
    hero = hero_data.iat[index[0], 2]
    hero_pic = hero_data.iat[index[0], 6]
    
    #Calculate Damage Taken by Heroes
    damage_taken = 0
    for instance, value in player['damage_taken'].items():
        if 'hero' in instance:
            damage_taken += value
            
    #Get Name
    name = player['personaname']
    if player['name'] != None:
       name = ''.join(i for i in player['name'] if ord(i)<128)
    
    #Observer and Sentry Durations
    obs_durations = []
    sentry_durations = []
    if len(player['obs_log']) > 0:
        for obs in player['obs_log']:
            time, handle = obs['time'], obs['ehandle']
            try:
                time_des = obs_frame[obs_frame['Ward ID'] == obs['ehandle']].iat[0, 0]
            except:
                time_des = game['duration']
            time_alive = time_des - time
            if time_alive > 360:
                time_alive = 360
            obs_durations.append(time_alive)
    if len(player['sen_log']) > 0:
        for sen in player['sen_log']:
            time, handle = sen['time'], sen['ehandle']
            try:
                time_des = sen_frame[sen_frame['Ward ID'] == sen['ehandle']].iat[0, 0]
            except:
                time_des = game['duration']
            time_alive = time_des - time
            if time_alive > 360:
                time_alive = 360
            sentry_durations.append(time_alive)   
    sum_obs = 0
    sum_sen = 0
    if len(obs_durations) > 0:
        sum_obs = np.sum(obs_durations)
    if len(sentry_durations) > 0:
        sum_sen = np.sum(sentry_durations)
    role = 0
    impact = 0
    start_date = datetime.date.fromtimestamp(game['start_time']).strftime("%Y-%m-%d")
    
    # Populate Player Frame
    player_frame = pd.DataFrame(
                [(game['match_id'], player['account_id'], name, hero, hero_pic, game['duration'],
                player['kills'], player['deaths'], player['assists'], player['last_hits'],
                player['denies'], player['benchmarks']['lhten']['raw'], player['dn_t'][10], 
                player['gold_per_min'], player['xp_per_min'], player['hero_damage'], player['hero_healing'],
                damage_taken, player['tower_damage'], player['tower_kills'], player['camps_stacked'],
                player['obs_placed'], sum_obs, player['observer_kills'], player['sen_placed'],
                sum_sen, player['sentry_kills'], player['teamfight_participation'], 
                player['stuns'], player['firstblood_claimed'], player['rune_pickups'], player['roshan_kills'],
                player['lane_role'], role, fscore, impact)],
        columns = ['Match ID', 'Account ID', 'Player', 'Hero', 'Hero Picture',
                'Game Length', 'Kills', 'Deaths', 'Assists', 'Last Hits', 'Denies', 'LH@10',
                'Den@10', 'GPM', 'XPM', 'Hero Damage', 'Hero Healing', 'Damage Taken',
                'Tower Damage', 'Tower Kills', 'Camps Stacked', 'Obs Placed', 'Total Obs Duration',
                'Obs Killed', 'Sentry Placed', 'Total Sentry Duration', 'Sentry Killed', 
                'Teamfight Participation', 'Stun Duration', 'First Blood', 'Rune Pickup',
                'Roshan Kills', 'Lane Role', 'Role', 'Fantasy Points', 'Impact'])
    return player_frame
    
def make_db(raw_file, OUT, type = 'Ama', pos = 'NA'):
    '''populate database file with legible match-stats'''
    
    # To convert hero_id into hero name
    heroStats = os.path.join('Data', 'heroStats.json')
    if not os.path.isfile(heroStats):
        get_herostats(heroStats)
    with open(heroStats, "r") as hs:
        hero_dict = json.load(hs)
        hero_data = pd.DataFrame.from_dict(hero_dict)    

    #Prepare DataFrame
    rd2l_data = pd.DataFrame()
                                            
    with open(raw_file, "r") as raw:
        raw_data = json.load(raw)
                                                                                       
    with open(OUT, "w") as out_file:
        clash = 0
        for game in raw_data:
            print("Checking Game %s"%game['match_id'])
            role_score = 0
            gamers=[]
            obs_frame, sen_frame = ward_list(game)
            for player in game['players']:
                player_frame = prune_data(player, game, hero_data, obs_frame, sen_frame)
                role = 0
                #Attempt role detection
                player_frame.to_csv('temp.csv', index = False)
                name = player['personaname']
                role = int(get_roles(os.path.join('Data', 'role_model.joblib'), 'temp.csv'))
                if type == 'Pro':
                    if player['name'] == None:
                        name = player['personaname']
                    else:
                        name = ''.join(i for i in player['name'] if ord(i)<128)
                    if name == '':
                        name = player['personaname']
                    role_db = pos[pos['Player'] == name]
                    if len(role_db['Position']) > 0:
                        role = role_db.iat[0, 1]
                    else:
                        role = int(input("%s"%name))
                        new_row = pd.DataFrame([(name, role)], columns = ["Player", "Position"])
                        pos = pos.append(new_row, ignore_index = True)
                    if role == 1 or role == 3 or role == 2:
                        if role != player['lane_role']:
                            role = int(get_roles('role_model.joblib', 'temp.csv'))
                            print("Predicted %s for %s"%(role, name))
                role_score += role
                player_frame["Role"] = role
                rd2l_data = rd2l_data.append(player_frame, ignore_index = True)
                os.remove('temp.csv')
                gamers.append([name, role])
            if (role_score != 30):
                print("Check %s"%game['match_id'])
                gamerframe = pd.DataFrame(gamers, columns = ["Name", "Role"])
                print(gamerframe)
                clash += 1
        print(clash)        
        #Write DB to file        
        rd2l_data.to_csv(OUT, index = False)
        if type == 'Pro':
            pos.to_csv('pos_cor.dat', index = False)
        
def ward_list(game):
    obs_list = []
    sen_list = []
    for player in game['players']:
        if len(player['obs_left_log']) > 0:
            for obs_des in player['obs_left_log']:
                obs_left = (obs_des['time'], obs_des['ehandle'])
                obs_list.append(obs_left)

        if len(player['sen_left_log']) > 0:
            for sen_des in player['sen_left_log']:
                sen_left = (sen_des['time'], sen_des['ehandle'])
                sen_list.append(sen_left)
                
    obs_frame = pd.DataFrame(obs_list, columns = ['Time Destroyed', 'Ward ID'])
    sen_frame = pd.DataFrame(sen_list, columns = ['Time Destroyed', 'Ward ID'])    

    return obs_frame, sen_frame
    
def calc_impact(player, game):
    return 0    
    
def makeimage(folder, player_names, point_list, date):
    '''generate a fantasy dream team image'''
    #Generate Fantasy Team Image
    top = 50
    p_top = top + 72
    h_top = p_top + 162
    a = Image.open(os.path.join('Data', 'fantasy_template.png')).resize((1374, 459), resample = 1)
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
    cols = (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22 ,23, 24, 25, 26, 27, 28, 30, 31, 32, 33)
    rfc = load(model)
    rd2l_set = pd.read_csv(data, usecols=cols)
    rd2l_X = rd2l_set.values[:, :len(cols)-1]
    rd2l_Y = rd2l_set.values[:, len(cols)-1]
    rd2l_predictions = rfc.predict(rd2l_X)
    return rd2l_predictions    