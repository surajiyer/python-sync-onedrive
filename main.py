"""
Resources:
	* https://keathmilligan.net/automate-your-work-with-msgraph-and-python#:~:text=The%20Microsoft%20Graph%20API%20gives%20you%20access%20to,with%20Graph%20to%20automate%20every%20day%20work%20tasks.
"""
import atexit
import logging
import msal
import os.path
import requests
from typing import List
import urllib.parse
from watchgod import watch, DefaultWatcher, Change
import yaml


ENDPOINT = 'https://graph.microsoft.com/v1.0'


def get_logger():
	log_configs = {
		'level': logging.INFO,
		'format': '%(asctime)s %(filename)s:%(lineno)d %(levelname)s  %(message)s',
		'datefmt': '%Y-%m-%d %X'
	}
	logging.basicConfig(**log_configs)
	return logging.getLogger()


def authenticate(logger=None):
	CLIENT_ID = os.environ['CLIENT_ID']
	AUTHORITY = f'https://login.microsoftonline.com/consumers/'
	SCOPES = [
		'Files.ReadWrite.All',
		'User.Read',
	]

	# Token caching
	# Each time you run the minimal example above, you will have to
	# click on the link and log in with your web browser. We can avoid
	# having to do this every time by adding a serializable token cache
	# to the MSAL app when it is created:
	cache = msal.SerializableTokenCache()
	if os.path.exists('token_cache.bin'):
		cache.deserialize(open('token_cache.bin', 'r').read())

	atexit.register(
		lambda: open('token_cache.bin', 'w').write(cache.serialize())\
		if cache.has_state_changed else None)

	app = msal.PublicClientApplication(
		CLIENT_ID, authority=AUTHORITY, token_cache=cache)

	# get access token
	accounts = app.get_accounts()
	result = None
	if len(accounts) > 0:
		result = app.acquire_token_silent(SCOPES, account=accounts[0])

	if result is None:
		# leverage "device flow" authentication that allows us to authenticate
		# the app on behalf of a user rather then using an API key or having
		# to store and supply a username / password with each request
		flow = app.initiate_device_flow(scopes=SCOPES)
		if 'user_code' not in flow:
			raise Exception('Failed to create device flow')

		if logger:
			logger.info(flow['message'])

		result = app.acquire_token_by_device_flow(flow)

	if 'access_token' in result:
		access_token = result['access_token']
		result = requests.get(
			f'{ENDPOINT}/me',
			headers={'Authorization': 'Bearer ' + access_token})
		result.raise_for_status()
		if logger:
			logger.info(result.json())
	else:
		raise Exception('no access token in result')

	return access_token


class MultipleFilesWatcher(DefaultWatcher):

	def __init__(self, root_path : List[str]):
		self.watchers = [
		DefaultWatcher(p) for p in root_path]

	def check(self):
		all_changes = set()
		for watcher in self.watchers:
			changes = watcher.check()
			all_changes |= changes
		return all_changes


def event_listener(sources, logger=None):
	for p in sources.keys():
		logger.info(f'Set to watch {p}')

	# watch for changes to file and update
	for changes in watch(
		list(sources.keys()),
		watcher_cls=MultipleFilesWatcher):
		if logger:
			logger.info(changes)
		for c in changes:
			if c[0] == Change.modified:
				yield c[1]


def upload_file(sources, path, small, access_token):
	"""
	Parameters
	----------
	sources : Dict[str, Dict[str, Any]]
		Mapping from local file path to remote OneDrive path

	path : str
		Path to file locally

	small : boolean
		Is the path pointing to a small file (<4mb)?

	access_token : str
		Access token
	"""
	path_url = urllib.parse.quote(sources[path]['remote_path'])
	if small:
		result = requests.put(
			f'{ENDPOINT}/me/drive/root:/{path_url}:/content',
			headers={
				'Authorization': 'Bearer ' + access_token,
				'Content-type': 'application/binary'
			},
			data=open(path, 'rb').read()
		)
		return result
	else:
		raise NotImplemented('Large files uploading not implemented yet!')


def event_action(sources, access_token, logger=None):
	for path in event_listener(sources, logger):
		try:
			result = upload_file(
				sources, path, sources[path]['small'], access_token)
			result = dict(result.json())
			if logger:
				logger.info(result)
			if 'error' in result and\
				result['error']['code'] == 'InvalidAuthenticationToken':
				# if the token expired, re-authenticate and retry
				access_token = authenticate(logger)
				result = upload_file(
					sources, path, sources[path]['small'], access_token)
				result = dict(result.json())
				if logger:
					logger.info(result)
		except Exception as e:
			logger.error(e)


if __name__ == '__main__':
	logger = get_logger()
	with open('settings.yml', 'r') as f:
		settings = yaml.safe_load(f)
	os.environ['CLIENT_ID'] = settings['CLIENT_ID']
	access_token = authenticate(logger)
	event_action(settings['sources'], access_token, logger)
