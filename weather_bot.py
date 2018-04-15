#! /var/www/user538/data/.local/bin/python3
# -*- coding: utf-8 -*-

from time import sleep
from mysql.connector import MySQLConnection
from python_config import read_config
import datetime
import requests
import re
import logging
from vk_telegram import BotHandler


dbconfig = read_config(section='mysql')
tokens = read_config(section='tokens')

token = tokens['telegram']
ya_key = tokens['yandex']
apixu_key = tokens['apixu']
google_maps_key = tokens['google']
darksky_key = tokens['darksky']
history_days = 5

class Weather:
	def __init__(self, key=apixu_key):
		self.key = key
		self.api_url = 'http://api.apixu.com/v1/'

	def get_history(self, day, city, country):
		self.day = day
		self.city = city
		self.country = country
		method = 'history.json'
		data= {
			'key': self.key,
			'q': self.city + ' ' + self.country, 
			'dt': self.day,
		}
		response = requests.get(self.api_url + method, params=data)
		while True:
			try:
			    hourly = response.json()['forecast']['forecastday'][0]['hour']
			    break
			except:
			    continue
		result = []
		for i in range(0, 24):
			result.append(hourly[i]['temp_c'])
		return result

	def get_location(self, city, country):
		self.city = city
		self.country = country
		method = 'current.json'
		data= {
			'key': self.key,
			'q': self.city + ' ' + self.country
			}
		response = requests.get(self.api_url + method, params=data)
		result = response.json()['location']
		return result


# MySQL stuff

def table_exists(tablename):
	try:
		cursor.execute("""
			SELECT 1
			FROM `{}`
			LIMIT 1
			""".format(tablename))
		return True

	except:
		return False
def fetch_data_from_table(tablename):
	db_array = []
	try:
		cursor.execute("""
			SELECT *
			FROM `{}`
			""".format(tablename))
		row = cursor.fetchall()
		return row 
	except:
		raise
	return db_array #returns db_array
def clear_table(tablename):
	try:
		cursor.execute("""
			truncate `{}`
			""".format(tablename))
	except:
		raise    
def create_table(tablename):
	try:
		cursor.execute("""
			CREATE TABLE `{}`  (
			`date` char(10) NOT NULL,
			`temperature` TEXT DEFAULT NULL,
			PRIMARY KEY (`date`)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8
			""".format(tablename))
	except:
		raise
def delete_table(tablename):
	try:
		cursor.execute("""
			DROP  TABLE `{}`
			""".format(tablename))
	except:
		raise
def write_temps_to_table(tablename, dates, temps):
	def write_one_data_to_table(tablename, date, temp, conn=conn):
		try:
			conn.cursor().execute("""INSERT INTO `{}`   
				VALUES ('{}', '{}')""".format(tablename, date, temp))
			conn.commit()
		except:
			raise
	for i in range(len(dates)):
		write_one_data_to_table(tablename, dates[i], temps[i])
def update_user_time(chat_id, time):
	try:
		conn.cursor().execute("""UPDATE users   
			SET time = '{}'
			WHERE chat_id = {}""".format(time, chat_id))
		conn.commit()
	except:
		raise
def update_user_city(chat_id, city, country):
	try:
		conn.cursor().execute("""UPDATE users   
			SET city = '{}'
			WHERE chat_id = {}""".format(city, chat_id))
		conn.commit()
	except:
		raise

	try:
		conn.cursor().execute("""UPDATE users   
			SET country = '{}'
			WHERE chat_id = {}""".format(country, chat_id))
		conn.commit()
	except:
		raise

	timedelta = time_delta(city, country)
	try:
		conn.cursor().execute("""UPDATE users   
			SET timedelta = '{}'
			WHERE chat_id = {}""".format(timedelta, chat_id))
		conn.commit()
	except:
		raise
def create_new_user(chat_id, time=None, city=None, country=None, username=None, timedelta=None):
	if not time == None:    
		try:
			conn.cursor().execute("""INSERT INTO users (chat_id, time, username)
				VALUES ('{}', '{}', '{}')""".format(chat_id, time, username))
			conn.commit()
		except:
			raise
	elif not city == None:
		try:
			conn.cursor().execute("""INSERT INTO users (chat_id, city, country, username, timedelta)
				VALUES ('{}', '{}', '{}', '{}', '{}')""".format(chat_id, city, country, username, timedelta))
			conn.commit()
		except:
			raise
def delete_user(chat_id):
	try:
		conn.cursor().execute("""
			DELETE FROM users
			WHERE chat_id = {}
			""".format(chat_id))
		conn.commit()
	except:
		raise

#####################

# Weather stuff

def n_days_ago_date(n):
	today = str(datetime.date.today())
	return (datetime.datetime.strptime(today, '%Y-%m-%d') - datetime.timedelta(n)).strftime('%Y-%m-%d') 
def last_n_dates(days=5):
	dates = []
	for date in range(days+1):
		dates.append(n_days_ago_date(date))
	dates = dates[:0:-1]
	return dates
def db_dates(db_array):
	dates = []
	for i in range(len(db_array)):
		dates.append(db_array[i][0])
	return dates
def db_temps(db_array):
	temperatures = []
	for i in range(len(db_array)):
		temp_list = [float(x) for x in db_array[i][1][1:(len(db_array[i][1])-1)].split(', ')]
		temperatures.append(temp_list)
	return temperatures
def dates_shift(db_array, tablename, days=history_days):
	dates = db_dates(fetch_data_from_table(tablename))
	last_dates = last_n_dates(days)
	shift = 0
	i = 0
	for i in range(len(dates)):
		if dates[i] == last_dates[0]:
			shift = i
			break
	if i == len(dates) - 1 and shift == 0:
		shift = len(dates)
	return shift
def missing_days_temp(shift, city, country):
	shifted_temp = []
	for i in range(shift):
		shifted_temp.append(weather.get_history(n_days_ago_date(shift-i), city, country))
	return shifted_temp
def today_left_hours(timedelta):
	now = datetime.datetime.today()
	timedelta = datetime.timedelta(seconds=float(timedelta))
	now_zoned = now + timedelta
	now_hour = int(datetime.datetime.strftime(now_zoned, '%H'))
	hours_left = 24 - now_hour
	return hours_left
def todays_forecast(city, country, timedelta):
	def city_to_coordinats(city, country):
		params = {
			'address': city + '+' + country,
			'key': google_maps_key
		}
		url = 'https://maps.googleapis.com/maps/api/geocode/json'
		response = requests.get(url, params).json()
		result = response['results'][0]['geometry']['location']
		return result	
	coordinates = city_to_coordinats(city, country)
	lat = str(coordinates['lat'])
	lng = str(coordinates['lng'])
	
	params = {
		'exclude': 'currently,daily',
		'units': 'si'
	}
	url = 'https://api.darksky.net/forecast/'
	while True:
		try:
			response = requests.get(url+darksky_key+'/'+lat+','+lng, params).json()
			break
		except:
			continue
	hourly = response['hourly']['data']
	
	today_hourly_temps = []
	today_hourly_conds = []
	today_hourly_windspeeds = []
	today_hourly_windgusts = []
	
	for i in range(today_left_hours(timedelta)):
		today_hourly_temps.append(hourly[i]['temperature'])
		today_hourly_conds.append(hourly[i]['icon'])
		today_hourly_windspeeds.append(hourly[i]['windSpeed'])
		today_hourly_windgusts.append(hourly[i]['windGust'])

	return {
		'temps': today_hourly_temps,
		'conds': today_hourly_conds,
		'windspeeds': today_hourly_windspeeds,
		'windgusts': today_hourly_windgusts
	}
def new_dates(db_dates, missing_dates, shift):
	db_dates = db_dates[shift:]
	new_dates = db_dates + missing_dates
	return new_dates
def new_temps(db_temps, missing_temps, shift):
	db_temps = db_temps[shift:]
	new_temps = db_temps + missing_temps
	return new_temps
def temp_message(temps, today_temp):
	def average(temps):
		return sum(temps)/float(len(temps))
	
	def std_deviation(temps):
		average_temps = average(temps)
		variance = 0
		for day in temps:
			variance += (average_temps - day) ** 2
		return ( variance / len(temps) ) ** 0.5
	
	forecast_start_hour = 24 - len(today_temp)
	days_mins = []
	days_maxs = []

	now_temp = today_temp[0]

	for day in range(len(temps)):
		temps[day] = temps[day][forecast_start_hour:]

	for day in range(len(temps)):
		days_mins.append(min(temps[day]))
		days_maxs.append(max(temps[day]))

	today_min = min(today_temp)
	today_max = max(today_temp)
	
	mins_average = average(days_mins)
	mins_std_dev = std_deviation(days_mins)
	yesterday_min = days_mins[len(days_mins)-1]
	diff_mins_aver_and_today = abs(mins_average - today_min)
	diff_mins_yest_and_today = abs(yesterday_min - today_min)
	
	maxs_average = average(days_maxs)
	maxs_std_dev = std_deviation(days_maxs)
	yesterday_max = days_maxs[len(days_maxs)-1]
	diff_maxs_aver_and_today = abs(maxs_average - today_max)
	diff_maxs_yest_and_today = abs(yesterday_max - today_max)

	message = ''
	message_temp = ''
	message_min = ''
	message_max = ''
	
	'''
	if diff_mins_yest_and_today > mins_std_dev: # or diff_mins_aver_and_today > mins_std_dev:
		if yesterday_min < today_min:
			message_min = str(round(today_min)).replace('.', ',')
			min_direction = 'up'
		else:
			message_min = str(round(today_min)).replace('.', ',')
			min_direction = 'down'
	
	if diff_maxs_yest_and_today > maxs_std_dev: # or diff_maxs_aver_and_today > maxs_std_dev:
		if yesterday_max < today_max:
			message_max = str(round(today_max)).replace('.', ',')
			max_direction = 'up'
		else:
			message_max = str(round(today_max)).replace('.', ',')
			max_direction = 'down'
	
	if message_min and message_max:
		if not message_min == message_max:
			if min_direction == 'up' and max_direction == 'up':
				message = 'Сегодня теплее, чем вчера, от {}° до {}°\xa0C. '.format(message_min, message_max)
			elif min_direction == 'down' and max_direction == 'down':
				message = 'Сегодня холоднее, чем вчера, от {}° до {}°\xa0C. '.format(message_min, message_max)
			else:
				message = 'Сегодня от {}° до {}°\xa0C. '.format(message_min, message_max)
		else:
			if min_direction == 'up' or max_direction == 'up':
				message = 'Сегодня теплее, чем вчера, {}°\xa0C. '.format(message_min)
			else:
				message = 'Сегодня холоднее, чем вчера, {}°\xa0C. '.format(message_min)
	elif message_min:
		if min_direction == 'up':
			message = 'Сегодня теплее, чем вчера, температура не опустится ниже {}°\xa0C. '.format(message_min)
		else:
			message = 'Сегодня холоднее, чем вчера, минимальная температура опустится до {}°\xa0C. '.format(message_min)
	elif message_max:
		if max_direction == 'up':
			message = 'Сегодня теплее, чем вчера, максимальная температура поднимется до {}°\xa0C. '.format(message_max)
		else:
			message = 'Сегодня холоднее, чем вчера, температура не поднимется выше {}°\xa0C. '.format(message_max)
	'''
	min_big_diff = False
	max_big_diff = False

	if diff_mins_yest_and_today > mins_std_dev: # or diff_mins_aver_and_today > mins_std_dev:
		min_big_diff = True

	if diff_maxs_yest_and_today > maxs_std_dev: # or diff_maxs_aver_and_today > maxs_std_dev:
		max_big_diff = True


	if yesterday_min < today_min:
		message_min = str(round(today_min)).replace('.', ',')
		min_direction = 'up'
	else:
		message_min = str(round(today_min)).replace('.', ',')
		min_direction = 'down'

	if yesterday_max < today_max:
		message_max = str(round(today_max)).replace('.', ',')
		max_direction = 'up'
	else:
		message_max = str(round(today_max)).replace('.', ',')
		max_direction = 'down'

	if min_direction == 'up' and max_direction == 'up': 
		if min_big_diff or max_big_diff:
			message = 'Сегодня теплее, чем вчера, от\xa0{}° до\xa0{}°\xa0C. '
		else:
			message = 'Температура сегодня от\xa0{}° до\xa0{}°\xa0C. ' # как вчера
	elif min_direction == 'down' and max_direction == 'down':
		if min_big_diff or max_big_diff:
			message = 'Сегодня холоднее, чем вчера, от\xa0{}° до\xa0{}°\xa0C. '
		else:
			message = 'Температура сегодня от\xa0{}° до\xa0{}°\xa0C. ' # как вчера
	elif min_big_diff and not max_big_diff:
		if min_direction == 'down':
			message = 'Сегодня холоднее, чем вчера, от\xa0{}° до\xa0{}°\xa0C. '
		else:
			message = 'Сегодня теплее, чем вчера, от\xa0{}° до\xa0{}°\xa0C. '
	elif max_big_diff and not min_big_diff:
		if max_direction == 'down':
			message = 'Сегодня холоднее, чем вчера, от\xa0{}° до\xa0{}°\xa0C. '
		else:
			message = 'Сегодня теплее, чем вчера, от\xa0{}° до\xa0{}°\xa0C. '
	elif not max_big_diff and not min_big_diff:
		message = 'Температура сегодня от\xa0{}° до\xa0{}°\xa0C. ' # как вчера
	else:
		message = 'Температура сегодня от\xa0{}° до\xa0{}°\xa0C. '
	return message.format(message_min, message_max)

def condition_message(conditions, winds):
	forecast_start_hour = 24-len(conditions)
	rain_time = [i+forecast_start_hour for i,x in enumerate(conditions) if x=='rain']
	snow_time = [i+forecast_start_hour for i,x in enumerate(conditions) if x=='snow']
	sleet_time = [i+forecast_start_hour for i,x in enumerate(conditions) if x=='sleet']
	fog_time = [i+forecast_start_hour for i,x in enumerate(conditions) if x=='fog']
	
	wind_warning = True if max(winds) > 10 else False
		
	rain_morning = False
	rain_day = False
	rain_evening = False
	if rain_time:
		for time in rain_time:
			if 9 <= time < 12 and rain_morning == False:
				rain_morning = True
			if 12 <= time < 18 and rain_day == False:
				rain_day = True
			if 18 <= time < 24 and rain_evening == False:
				rain_evening = True

	snow_morning = False
	snow_day = False
	snow_evening = False
	if snow_time:
		for time in snow_time:
			if 9 <= time < 12 and snow_morning == False:
				snow_morning = True
			if 12 <= time < 18 and snow_day == False:
				snow_day = True
			if 18 <= time < 24 and snow_evening == False:
				snow_evening = True
			
	sleet_morning = False
	sleet_day = False
	sleet_evening = False
	if sleet_time:
		for time in sleet_time:
			if 9 <= time < 12 and sleet_morning == False:
				sleet_morning = True
			if 12 <= time < 18 and sleet_day == False:
				sleet_day = True
			if 18 <= time < 24 and sleet_evening == False:
				sleet_evening = True

	fog_morning = False
	fog_day = False
	fog_evening = False
	if fog_time:
		for time in fog_time:
			if 9 <= time < 12 and fog_morning == False:
				fog_morning = True
			if 12 <= time < 18 and fog_day == False:
				fog_day = True
			if 18 <= time < 24 and fog_evening == False:
				fog_evening = True

	wind_morning = []
	wind_day = []
	wind_evening = []
	if wind_warning:
		wind_time = [i+forecast_start_hour for i,x in enumerate(winds) if x > 10]
		for time in wind_time:
			if 9 <= time < 12:
				wind_morning.append(winds[time-forecast_start_hour])
			if 12 <= time < 18:
				wind_day.append(winds[time-forecast_start_hour])
			if 18 <= time < 24:
				wind_evening.append(winds[time-forecast_start_hour])
				
		try:
			wind_morning = round(max(wind_morning))
		except:
			pass
		try:
			wind_day = round(max(wind_day))
		except:
			pass
		try:
			wind_evening = round(max(wind_evening))
		except:
			pass
		
			
	message = ''
	message_morning = ''
	message_day = ''
	message_evening = ''
	
	if rain_morning or snow_morning or sleet_morning or fog_morning or wind_morning:
		if rain_morning:
			message_morning += ' дождь'
			
		if snow_morning:
			if rain_morning:
				if sleet_morning or fog_morning:
					message_morning += ', снег'
				else:
					message_morning += ' и\xa0снег'
			else:
				message_morning += ' снег'
		
		if sleet_morning:
			if rain_morning or snow_morning:
				if fog_morning:
					message_morning += ', дождь со\xa0снегом'
				else:
					message_morning += ' и\xa0дождь со\xa0снегом'
			else:
				message_morning += ' дождь со\xa0снегом'
		
		if fog_morning:
			if rain_morning or snow_morning or sleet_morning:
				message_morning += ' и\xa0туман'
			else:
				message_morning += ' туман'
				
		if wind_morning:
			if rain_morning or snow_morning or sleet_morning or fog_morning and not ():
				message_morning += ', а\xa0ветер до\xa0{}\xa0м/с.'.format(wind_morning)
			else:
				message_morning += ' ветер до\xa0{}\xa0м/с.'.format(wind_morning)
		else:
			message_morning += '. '
				
	if rain_day or snow_day or sleet_day or fog_day or wind_day:
		if rain_day:
			message_day += ' дождь'
			
		if snow_day:
			if rain_day:
				if sleet_day or fog_day:
					message_day += ', снег'
				else:
					message_day += ' и\xa0снег'
			else:
				message_day += ' снег'
		
		if sleet_day:
			if rain_day or snow_day:
				if fog_day:
					message_day += ', дождь со\xa0снегом'
				else:
					message_day += ' и\xa0дождь со\xa0снегом'
			else:
				message_day += ' дождь со\xa0снегом'
		
		if fog_day:
			if rain_day or snow_day or sleet_day:
				message_day += ' и\xa0туман'
			else:
				message_day += ' туман'
		
		if wind_day:
			if rain_day or snow_day or sleet_day or fog_day and not ():
				message_day += ', а\xa0ветер до\xa0{}\xa0м/с.'.format(wind_day)
			else:
				message_day += ' ветер до\xa0{}\xa0м/с.'.format(wind_day)
		else:
			message_day += '. '
	
	if rain_evening or snow_evening or sleet_evening or fog_evening or wind_evening:
		if rain_evening:
			message_evening += ' дождь'
			
		if snow_evening:
			if rain_evening:
				if sleet_evening or fog_evening:
					message_evening += ', снег'
				else:
					message_evening += ' и\xa0снег'
			else:
				message_evening += ' снег'
		
		if sleet_evening:
			if rain_evening or snow_evening:
				if fog_evening:
					message_evening += ', дождь со\xa0снегом'
				else:
					message_evening += ' и\xa0дождь со\xa0снегом'
			else:
				message_evening += ' дождь со\xa0снегом'
		
		if fog_evening:
			if rain_evening or snow_evening or sleet_evening:
				message_evening += ' и\xa0туман'
			else:
				message_evening += ' туман'
		
		if wind_evening:
			if rain_evening or snow_evening or sleet_evening or fog_evening and not ():
				message_evening += ', а\xa0ветер до\xa0{}\xa0м/с.'.format(wind_evening)
			else:
				message_evening += ' ветер до\xa0{}\xa0м/с.'.format(wind_evening)
		else:
			message_evening += '. '

	if message_morning == message_day and message_morning == message_evening and message_morning:
		message += 'Весь день' + message_morning

	elif message_morning == message_day and message_morning:
		message += 'Утром и\xa0днём' + message_morning
		if message_evening:
			message += 'А\xa0вечером' + message_evening

	elif message_morning == message_evening and message_morning:
		message += 'Утром и\xa0вечером' + message_morning
		if message_day:
			message += 'А\xa0днём' + message_day

	elif message_day == message_evening and message_day:
		if message_morning:
			message += 'Утром' + message_morning + ', а\xa0днём и\xa0вечером' + message_day
		else:
			message += 'Днём и\xa0вечером' + message_day

	else:
		if message_morning:
			message += 'Утром' + message_morning
		if message_day:
			if not message_morning or message_evening:
				message += 'Днём' + message_day
			else:
				message += 'А\xa0днём' + message_day
		if message_evening:
			if not message_morning or not message_day:
				message += 'Вечером' + message_evening
			else:
				message += 'А\xa0вечером' + message_evening
				
	return message

#####################

# City and time stuff

def check_chat_id(chat_id):
	try:
		cursor.execute("""
			SELECT {}
			FROM users
			WHERE chat_id = {}
			GROUP BY chat_id
			""".format(chat_id, chat_id))
	except:
		raise
	exists = cursor.fetchone()
	if exists:
		return True
	else:
		return False
def get_user_info(chat_id):
	try:
		cursor.execute("""
			SELECT city, country, time, username, timedelta
			FROM users
			WHERE chat_id={}
			""".format(chat_id))
		info = cursor.fetchone()
	except:
		raise
	return {
	'city': info[0],
	'country': info[1],
	'time': info[2],
	'username': info[3],
	'timedelta': info[4]
	}
def is_time(text):
	time_pat_2 = re.compile('[0-9][0-9]:[0-9][0-9]')
	time_pat_1 = re.compile('[0-9]:[0-9][0-9]')
	if time_pat_2.match(text) or time_pat_1.match(text):
		if int(text.split(':')[0]) < 24 and int(text.split(':')[1]) < 60:
			return True
		else:
			return False
	else:
		return False
def city_info(city, country):
	city_and_country = city + ' ' + country
	response = weather.get_location(city, country)
	location = {
	'city': response['name'],
	'country': response['country'],
	'localtime': response['localtime']
	}
	return location
def is_city(text):
	text = text.lower()
	parts = text.split(',')
	with open('cities.txt', 'r') as city_list:
		cities = [line.strip() for line in city_list]
	with open('countries.txt', 'r') as countries_list:
		countries = [line.strip() for line in countries_list]
	result = False
	city = ''
	country = ''
	for part in parts:
		while part[0] == ' ':
			part = part[1:]
		while part[len(part)-1] == ' ':
			part = part[:len(part)-1]
		try:
			translated = translate(part, 'en').lower()
		except:
			translated = ''
		transliterated = translit(part)
		for c in cities:
			if c.lower() == transliterated or c.lower() == translated:
				city = c.lower()
				break
		for c in countries:
			if c.lower() == transliterated or c.lower() == translated:
				country = c.lower()
				break
	if not city == '':
		if city == 'moscow' and country == '':
			country = 'russia'
		if city == 'ufa':
			city = 'oufa'
		check = city_info(city, country)
		if city == check['city'].lower() and country == check['country'].lower() or country == '':
			result = {
			'city': check['city'],
			'country': check['country']
			}
	print(result)
	return result
def time_delta(city, country):
	localtime_str = city_info(city, country)['localtime']
	localtime = datetime.datetime.strptime(localtime_str, '%Y-%m-%d %H:%M')
	localtime = localtime.replace(microsecond=0,second=0,minute=0)
	utctime = datetime.datetime.now().replace(microsecond=0,second=0,minute=0)
	delta = localtime - utctime
	return delta.total_seconds()
def str_to_delta(str):
	delta = datetime.timedelta(seconds=float(str))
	return delta

#####################

# Notification stuff

def from_users(db_array, mode):
	if mode == 'id':
		ids = []
		for i in range(len(db_array)):
			ids.append(db_array[i][0])
		return ids
	elif mode == 'time':
		times = []
		for i in range(len(db_array)):
			times.append(db_array[i][3])
		deltas = []
		for i in range(len(db_array)):
			deltas.append(db_array[i][5])

		results = []
		for i in range(len(times)):
			if not times[i] == None and not deltas[i] == None :
				time = datetime.datetime.strptime(times[i], '%H:%M')
				delta = str_to_delta(deltas[i])
				result = time - delta
				results.append(datetime.datetime.strftime(result, '%H:%M'))
			else:
				results.append(times[i])
		return results
	elif mode == 'city':
		cities = []
		for i in range(len(db_array)):
			cities.append(db_array[i][1])
		return cities
	elif mode == 'country':
		cities = []
		for i in range(len(db_array)):
			cities.append(db_array[i][2])
		return cities
	elif mode == 'timedelta':
		timedeltas = []
		for i in range(len(db_array)):
			timedeltas.append(db_array[i][5])
		return timedeltas
def check_time(time):
	now = datetime.datetime.strftime(datetime.datetime.today(), '%H:%M')
	if time == now:
		return time
	else:
		return False
def weather_notification(city, country, timedelta):
	city_and_country = city + '_' + country
	db_data = fetch_data_from_table(city_and_country)
	shift = dates_shift(db_data, city_and_country)
	forecast_for_today = todays_forecast(city, country, timedelta)
	missing = missing_days_temp(shift, city, country)
	new_temps_list = new_temps(db_temps(db_data), missing, shift)
	now_temp = round(forecast_for_today['temps'][0])
	message = temp_message(new_temps_list, forecast_for_today['temps']) + condition_message(forecast_for_today['conds'], forecast_for_today['windspeeds']) + 'Сейчас температура {}°\xa0C.'.format(now_temp)
	print('Сообщение отправлено')
	return message

#######################

def answer(mode, last_chat_id, last_chat_text, last_chat_name, usertime, usercity):
	if mode == 'help':
		message = "Чтобы изменить время уведомлений, введите его, например, 9:00.\n\n\
Чтобы выбрать другой город, введите его название. Если страна определилась неправильно, введите названия города и\xa0страны через запятую, например, Москва, Россия.\n\n\
Чтобы прекратить использование бота, отправьте команду /stop"
	elif mode == 'stop':
		message = 'Ок, больше не\xa0буду присылать уведомления.'
		delete_user(last_chat_id)
	elif mode == 'time':
		if len(last_chat_text) == 5 and last_chat_text[0] == '0':
			last_chat_text = last_chat_text[1:]
		if usertime == None:
			message = 'Теперь, каждый день в\xa0' + last_chat_text + ' буду анализировать прогноз погоды и\xa0присылать уведомление о\xa0грядущих изменениях.\n\n\
Чтобы изменить время уведомлений, отправьте сообщение, например, 9:00.\n\nЧтобы выбрать другой город, введите название.'
		else:
			message = 'Ок, теперь буду проверять погоду в\xa0' + last_chat_text + "."
		update_user_time(last_chat_id, last_chat_text)
	elif mode == 'city':
		city_rus = translate(last_chat_text['city'], 'ru')
		country_rus = translate(last_chat_text['country'], 'ru')
		if usercity == None:
			message = 'Выбран город — ' + city_rus.title() + ', ' + country_rus.title() + '. Чтобы выбрать другой город, просто введите его название.\n\nЧтобы изменить время уведомлений, введите его, например, 9:00.'
		else:
			if city_rus[0] == 'в' and not second_letter_vocable(city_rus):
				message = 'Ок, теперь буду проверять погоду во\xa0' + decline(city_rus).title() + ', ' + country_rus + "."
			else:
				message = 'Ок, теперь буду проверять погоду в\xa0' + decline(city_rus).title() + ', ' + country_rus + "."
		update_user_city(last_chat_id, last_chat_text['city'].title(), last_chat_text['country'].title())
	elif mode == 'notime':
		message = 'Укажите время, когда вы хотите получать уведомления, например, 9:00.'
	elif mode == 'nocity':
		message = 'Укажите город, для которого вы хотите получать уведомления.'
	else:
		message = 'Проверяю погоду в\xa0%s каждый день в\xa0%s.' % (decline(translate(usercity, 'ru')).title(), usertime)
	bot.send_message(last_chat_id, message)
	print(message, 'for', last_chat_id, last_chat_name)

def answer_to_new_user(mode, last_chat_id, last_chat_text, last_chat_name):
	if mode == 'help':
		message = "Чтобы изменить время уведомлений, введите его, например, 9:00.\n\n\
Чтобы выбрать другой город, введите его название. Если страна определилась неправильно, введите названия города и страны через запятую, например, Москва, Россия.\n\n\
Чтобы прекратить использование бота, отправьте команду /stop"
	elif mode == 'stop':
		message = 'Никогда уведомления не\xa0присылал, нечего и\xa0начинать.'
	elif mode == 'time':
		if len(last_chat_text) == 5 and last_chat_text[0] == '0':
			last_chat_text = last_chat_text[1:]
		message = 'Теперь, каждый день в ' + last_chat_text + ' буду анализировать прогноз погоды и\xa0присылать уведомление о\xa0грядущих изменениях. Для завершения настройки укажите город, в\xa0котором нужно проверять погоду'
		create_new_user(last_chat_id, time=last_chat_text, username=last_chat_name)
	elif mode == 'city':
		city = last_chat_text['city']
		country = last_chat_text['country']
		city_rus = translate(city, 'ru')
		country_rus = translate(country, 'ru')
		message = 'Выбран город — ' + city_rus.title() + ', ' + country_rus.title() + '. Если страна определилась неправильно, введите названия города и\xa0страны через запятую, например, Москва, Россия.\n\n\
Укажите время, когда вы хотите получать уведомления, например, 9:00'
		create_new_user(last_chat_id, city=last_chat_text['city'].title(), country=last_chat_text['country'].title(), username=last_chat_name, timedelta=time_delta(city, country))
	else:
		message = 'Укажите город, в\xa0котором нужно проверять погоду'
	
	bot.send_message(last_chat_id, message)
	print(message, 'for', last_chat_id, last_chat_name)

#######################

def decline(word):
	url = 'https://ws3.morpher.ru/russian/declension'
	params = {
	  's': word,
	  'format':"json"
	}
	response = requests.get(url, params)
	data = response.json()
	try:
		result = data['П']
	except:
		result = word
	return result
def second_letter_vocable(word):
	vocables = ['а','е','ё','и','о','у','ы','э','ю','я']
	result = 0
	for vocable in vocables:
		if word[1] == vocable:
		  result += 1
		  break

	if result == 1:
	  return True
	else:
	  return False
def translit(text, mode=False):
	text = text.lower()
	text = text.replace('а','a')
	text = text.replace('б','b')
	text = text.replace('в','v')
	text = text.replace('г','g')
	text = text.replace('д','d')
	text = text.replace('е','e')
	text = text.replace('ё','jo')
	text = text.replace('ж','zh')
	text = text.replace('з','z')
	text = text.replace('и','i')
	text = text.replace('й','y')
	text = text.replace('к','k')
	text = text.replace('л','l')
	text = text.replace('м','m')
	text = text.replace('н','n')
	text = text.replace('о','o')
	text = text.replace('п','p')
	text = text.replace('р','r')
	text = text.replace('с','s')
	text = text.replace('т','t')
	text = text.replace('у','u')
	text = text.replace('ф','f')
	text = text.replace('х','kh')
	text = text.replace('ц','c')
	text = text.replace('ч','ch')
	text = text.replace('ш','sh')
	text = text.replace('щ','shch')
	text = text.replace('ъ','')
	text = text.replace('ы','y')
	if mode == False:
		text = text.replace('ь','')
	else:
		text = text.replace('ь',"'")
	text = text.replace('э','e')
	text = text.replace('ю','ju')
	text = text.replace('я','ja')
	text = text.replace(',','')
	return text
def translate(text, lang):
	params = {
	'key': ya_key,
	'text': text,
	'lang': lang
	}
	url = 'https://translate.yandex.net/api/v1.5/tr.json/translate'
	response = requests.get(url, data=params)
	return response.json()['text'][0]

######################

weather = Weather()
bot = BotHandler(token)


print('Started')
bot.send_message(7664729, "Я воскрес!")

logging.basicConfig(level=logging.WARNING, filename='myapp.log')

def main():
	offset = bot.get_offset()
	while True:
		# Update data from database
		sent_status = False
		global conn
		global cursor
		conn = MySQLConnection(**dbconfig)
		cursor = conn.cursor(buffered=True)
		users_data = fetch_data_from_table('users')
		times_list = from_users(users_data, 'time')
		ids_list = from_users(users_data, 'id')
		cities_list = from_users(users_data, 'city')
		countries_list = from_users(users_data, 'country')
		timedeltas_list = from_users(users_data, 'timedelta')
		conn.close()
		while True:
			# Sending notifications
			if sent_status == False:
				matches = []
				for time_id in range(len(times_list)):
					if check_time(times_list[time_id]):
						matches.append(time_id)
				if matches:
					sent_status = 1
					conn = MySQLConnection(**dbconfig)
					cursor = conn.cursor(buffered=True)
					for match in matches:
						city = cities_list[match]
						if not city:
							continue
						country = countries_list[match]
						city_and_country = city + '_' + country
						if not table_exists(city_and_country):
							create_table(city_and_country)
							print('Table', city_and_country, 'created')
							write_temps_to_table(city_and_country, last_n_dates(), missing_days_temp(history_days, city, country))
						bot.send_message(ids_list[match], weather_notification(city, country, timedeltas_list[match]))
					conn.close()

			# Get Messages

			updates = bot.get_updates(offset, timeout=30)

			# Answering
			if updates:
				need_to_break = False
				conn = MySQLConnection(**dbconfig)
				cursor = conn.cursor(buffered=True)
				for update in updates:
					try:
						last_chat_text = update['last_chat_value']['text']
					except:
						last_chat_text = 'Не текст'
					last_chat_id = update['last_chat_id']
					last_chat_name = update['last_chat_name']
					last_update_id = update['last_update_id']

					print('Answering to', last_chat_text)
					text_is_city = is_city(last_chat_text)
					if check_chat_id(last_chat_id):
						print('User found in DB')
						user = get_user_info(last_chat_id)
						usertime = user['time']
						usercity = user['city']
						if last_chat_text == '/help':
							answer('help', last_chat_id, last_chat_text, last_chat_name, usertime, usercity)
							offset += 1
						elif last_chat_text == '/stop':
							answer('stop', last_chat_id, last_chat_text, last_chat_name, usertime, usercity)
							offset += 1
						elif is_time(last_chat_text):
							answer('time', last_chat_id, last_chat_text, last_chat_name, usertime, usercity)
							offset += 1
							need_to_break = True
							
						elif text_is_city:
							answer('city', last_chat_id, text_is_city, last_chat_name, usertime, usercity) 
							offset += 1
							need_to_break = True
													
						elif usertime == None:
							answer('notime', last_chat_id, last_chat_text, last_chat_name, usertime, usercity)
							offset += 1
						elif usercity == None:
							answer('nocity', last_chat_id, last_chat_text, last_chat_name, usertime, usercity)
							offset += 1
						else:
							answer(None, last_chat_id, last_chat_text, last_chat_name, usertime, usercity)
							offset += 1
					else:
						if last_chat_text == '/help':
							answer_to_new_user('help', last_chat_id, last_chat_text, last_chat_name)
							offset += 1
						elif last_chat_text == '/stop':
							answer_to_new_user('stop', last_chat_id, last_chat_text, last_chat_name)
							offset += 1
						elif is_time(last_chat_text):
							answer_to_new_user('time', last_chat_id, last_chat_text, last_chat_name)
							offset += 1
							need_to_break = True
						elif text_is_city:
							answer_to_new_user('city', last_chat_id, text_is_city, last_chat_name)
							offset += 1
							need_to_break = True
						else:
							answer_to_new_user(None, last_chat_id, last_chat_text, last_chat_name)
							offset += 1
				conn.close()
				if need_to_break:
					break

			# Increment
			if not sent_status == False:
				sent_status += 1
				if sent_status == 21:
					sent_status = False
			sleep(3)


if __name__ == '__main__':
	try:
		main()
	except:
		bot.send_message(7664729, "Я умер!")
		logging.exception("Oops:")