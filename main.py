from bs4 import BeautifulSoup
from couchpotato.core.helpers.encoding import simplifyString, tryUrlencode
from couchpotato.core.helpers.variable import tryInt
from couchpotato.core.logger import CPLog
from couchpotato.core.media._base.providers.torrent.base import TorrentMagnetProvider
from couchpotato.core.media.movie.providers.base import MovieProvider
import datetime
import traceback
import re

log = CPLog(__name__)


class CorsaroNero(TorrentMagnetProvider, MovieProvider):

	urls = {
		'test': 'http://ilcorsaronero.info',
		'base_url': 'http://ilcorsaronero.info',
		'detail': 'http://ilcorsaronero.info/tor/%d/%s',
		'search': 'http://ilcorsaronero.info/argh.php?search=%s',
	}

	cat_ids = [
		(1, ['dvdrip', '3d', '720p', '1080p', 'bd50', 'brrip']),
		(19, ['scr', 'r5', 'cam', 'ts', 'tc']),
		(20, ['dvdr'])
	]

	http_time_between_calls = 1  # seconds
	cat_backup_id = 1

	def _searchOnTitle(self, title, movie, quality, results):
		log.debug("Searching for %s (%s) on %s" % (title, quality['label'], self.urls['base_url']))

		# remove accents 
		simpletitle = simplifyString(title)
		cat = self.getCatId(quality)

		log.debug("Searching in CorSaRoNero title: %s" % (tryUrlencode(simpletitle)))
		data = self.getHTMLData(self.urls['search'] % (tryUrlencode(simpletitle)))

		if 'Nessus torrent trovato!!!!' in data:
			log.info("No torrents found for %s on ilCorsaroNero.info.", title)
			return
		
		if data:
			try:
				html = BeautifulSoup(data)
				entries_1 = html.findAll('tr', attrs={'class':'odd'})
				entries_2 = html.findAll('tr', attrs={'class':'odd2'})
			
				try:
					self.parseResults(results, entries_1, movie, title)
					self.parseResults(results, entries_2, movie, title)
				except:
					log.error('Failed parsing ilCorsaroNero: %s', traceback.format_exc())
						
			except AttributeError:
				log.debug('No search results found.')

	# computes days since the torrent release
	def ageToDays(self, age_str):
		dd_mm_yy = age_str.split('.')
		yyyy = int("20" + dd_mm_yy[2])		
		t1 = datetime.datetime(yyyy, int(dd_mm_yy[1]), int(dd_mm_yy[0]))
		t2 = datetime.datetime.now()
		# actually a datetime.timedelta object
		tdelta = t2 - t1
		# to int
		return tdelta.days

	# retrieves the magnet link from the detail page of the original torrent result
	def getMagnetLink(self, url):
		data = self.getHTMLData(url)
		html = BeautifulSoup(data)
		magnet = html.find('a', attrs={'class': 'forbtn'})['href']
		return magnet
	
	# filters the <td> elements containing the results, if any
	def parseResults(self, results, entries, movie, title):
		table_order = ['Cat', 'Name', 'Size', 'Azione', 'Data', 'S', 'L']
		
		for result in entries:
			new = {}
			nr = 0
	
			for td in result.find_all('td'):
				column_name = table_order[nr]
				if column_name:
	
					if column_name is 'Name':
						link = td.find('a', {'class': 'tab'})
						# extract the title from the real link instead of the text because in this case the text is cut and doesn't contain the full release name and tags and remove double "_" signs
						rel_name = re.sub('_+','_',link['href'].split('/')[5])
						if self.conf('ignore_year'):
							# ignore missing year option is set and there's no year in the release name
							words = re.split('\W+|_', title.lower())
							index = rel_name.lower().find(words[-1] if words[-1] != 'the' else words[-2]) + len(words[-1] if words[-1] != 'the' else words[-2]) +1
							index2 = index + 7
							if not str(movie['info']['year']) in rel_name[index:index2]:
							# couldnt find the year in the right place and ignore_year is set so remove other wrongly placed years
								rel_name = re.sub(str(movie['info']['year']),'',rel_name)
								rel_name = rel_name[0:index] + str(movie['info']['year']) + '_' + rel_name[index:]
								log.debug('Ignore year is set and we couldnt find the year in the release name, release name modified into: %s', rel_name)
						# Replace "_" with "." couchpotato already does that but for quality tags it's needed
						new['name'] = re.sub('_','.',rel_name)
					elif column_name is 'Size':
						new['size'] = self.parseSize(td.text)
					elif column_name is 'Azione':
						# retrieve download link
						new['detail_url'] = td.find('form')['action']
						new['id'] = new['detail_url'].split('/')[4]
						# fare richiesta detail url e prendere link magnet
						new['url'] = self.getMagnetLink(new['detail_url'])
					elif column_name is 'Data':
						new['age'] = self.ageToDays(td.find('font').text)
					elif column_name is 'S':
						seed = td.find('font').text
						if seed == "n/a":
							seed = "1"
						new['seeders'] = tryInt(seed)
					elif column_name is 'L':
						leech = td.find('font').text
						if leech == "n/a":
							leech = "1"
						new['leechers'] = tryInt(leech)
						### TODO: what about score extras here ??? ###
						new['score'] = 0
	
				nr += 1
	
			if nr == 7:  # only if we parsed all tds (i.e. category was right)
				results.append(new)
				log.debug("New result %s", new)
