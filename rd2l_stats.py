'''rd2l fantasy script V 0.1 by linoli ravioli. Call the script with an integer indicating how many days back to go when looking for games as the first argument'''
import requests
import json
import sys
import datetime
import pandas as pd
import os

stratz_URL = 'http://api.stratz.com/api/v1/'
opendota_URL = 'http://api.opendota.com/api/'
OUT = 'rd2l_fantasy_'+datetime.datetime.now().strftime("%Y-%m-%d")+'.out'
RAW = 'rd2l_fantasy_'+datetime.datetime.now().strftime("%Y-%m-%d")+'.raw'

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
        if game_date >= from_date:
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
    hero_dict = requests.get(opendota_URL+'heroStats/').json()
    hero_data = pd.DataFrame.from_dict(hero_dict)
    

    #Prepare DataFrame
    rd2l_data = pd.DataFrame([],columns = ["Full Match", "Start Time", "Account_id", "Player",
                                            "Fantasy Points", "Kills", "Deaths", "Assists",
                                            "Hero Damage", "Hero Healing", "Last Hits",
                                            "Denies", "GPM", "XPM", "Tow", "Tower Damage",
                                            "Ros", "TF","Obs Placed", "Camps Stacked", "Ru",
                                            "FB", "Stuns", "Hero","Game Length", "Total Kills",
                                            "FPPM", "Lane", "Role"])
    with open(raw_file, "r") as raw:
        raw_data = json.load(raw)
                                                                                       
    with open(OUT, "w") as out_file:
        for r in raw_data:
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
                
                #Populate DB
                start_date = datetime.date.fromtimestamp(r['start_time']).strftime("%Y-%m-%d")
                player_frame = pd.DataFrame(
                    [(r['match_id'], start_date, i['account_id'],i['personaname'], fscore, i['kills'],
                    i['deaths'], i['assists'],i['hero_damage'],i['hero_healing'],i['last_hits'],
                    i['denies'], i['gold_per_min'], i['xp_per_min'], i['tower_kills'], 
                    i['tower_damage'], i['roshan_kills'], tf_participation, i['obs_placed'],
                    i['camps_stacked'], i['rune_pickups'], fb, i['stuns'], hero, r['duration'], 
                    (r['dire_score']+r['radiant_score']), round(fscore*60/r['duration'],4),
                    i['lane'], i['lane_role'])],
                    columns = ["Full Match", "Start Time", "Account_id", "Player", 
                    "Fantasy Points", "Kills", "Deaths", "Assists", "Hero Damage", 
                    "Hero Healing", "Last Hits", "Denies", "GPM", "XPM", "Tow", 
                    "Tower Damage", "Ros", "TF","Obs Placed", "Camps Stacked", "Ru",
                    "FB", "Stuns", "Hero", "Game Length", "Total Kills", "FPPM",
                    "Lane", "Role"])
                rd2l_data = rd2l_data.append(player_frame, ignore_index = True)
                
        #Write DB to file        
        rd2l_data.to_csv(OUT, index = False)
        
#Check if days_back is given, set date after which to look for games
try: 
    sys.argv[1]
except:
    print("Please specify an integer as the first argument indicating how many days back to look for games.")
    sys.exit()
days_back = int(sys.argv[1])    
date = datetime.date.today() + datetime.timedelta(days = -days_back)

#Only make new DB if not existant yet
if not os.path.isfile(RAW):
    print("Fetching List of Games in last %s days."%days_back)
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

col_list = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 18, 19,26] #Columns to print

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
#Core
print("**Core**")
sort_data = rd2l_data[rd2l_data['Role']==3]
sort_data = sort_data.sort_values(by = 'Fantasy Points', ascending = False)
for i in [0, 1]:
    player = sort_data.iat[i, 3]
    points = sort_data.iat[i, 4]
    hero = sort_data.iat[i, 23]
    game = sort_data.iat[i, 0]
    print("\t%s on %s with %s (<https://www.opendota.com/matches/%s>)"%(player, points, hero, game))
print("**Mid**")
sort_data = rd2l_data[rd2l_data['Role']==2]
sort_data = sort_data.sort_values(by = 'Fantasy Points', ascending = False)
for i in [0]:
    player = sort_data.iat[i, 3]
    points = sort_data.iat[i, 4]
    hero = sort_data.iat[i, 23]
    game = sort_data.iat[i, 0]
    print("\t%s on %s with %s (<https://www.opendota.com/matches/%s>)"%(player, points, hero, game))
print("**Support**")
sort_data = rd2l_data[rd2l_data['Role']==1]
sort_data = sort_data.sort_values(by = 'Fantasy Points', ascending = False)
for i in [0, 1]:
    player = sort_data.iat[i, 3]
    points = sort_data.iat[i, 4]
    hero = sort_data.iat[i, 23]
    game = sort_data.iat[i, 0]
    print("\t%s on %s with %s (<https://www.opendota.com/matches/%s>)"%(player, points, hero, game))
