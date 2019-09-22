import fantasy_utils as fu
import datetime
import os
import pandas as pd

positions = pd.read_csv('ti_pos.dat')


stratz_URL = 'http://api.stratz.com/api/v1/'
opendota_URL = 'http://api.opendota.com/api/'
league_id = 10749
date = datetime.date(2019, 8, 14)

game_list = fu.get_games(league_id, date, 200)

fu.make_db('ti.raw', 'ti.out', type='Pro', pos=positions)