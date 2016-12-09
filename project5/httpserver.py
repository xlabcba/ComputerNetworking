from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import urllib2
import getopt
import sys
import os

class MyHTTPHandler(BaseHTTPRequestHandler):
	def __init__(self, cache, origin, *args):
		self.origin = origin
		self.cache = cache
		BaseHTTPRequestHandler.__init__(self, *args)

	def do_GET(self):
		# If request page in not in the cache
		if self.path not in self.cache:
			try:
				# request = 'http://' + self.origin + ':8080' + self.path
				request = 'http://' + self.origin + self.path
				print request
				response = urllib2.urlopen(request)
			except urllib2.HTTPError as he:
				self.send_error(he.code, he.reason)
				return
			except urllib2.URLError as ue:
				self.send_error(ue.reason)
				return
			else:
				self.download_from_origin(self.path, response)

		# Read cached file from local file
		with open(os.getcwd() + self.path) as request_page:
			self.send_response(200)
			self.send_header('Content-type', 'text/plain')
			self.end_headers()
			self.wfile.write(request_page.read())

		# Update the cache using LRU

	def download_from_origin(self, path, response):
		filename = os.getcwd() + self.path
		directory = os.path.dirname(filename)
		print 'directory: ', directory
		print 'filename: ', filename
		print 'os.getcwd():', os.getcwd()

		if not os.path.exists(directory):
			try:
				os.makedirs(directory)
			except:
				print "Can not make dir, exceed memory size limit"

		try:
			# Handle write exception
			f = open(filename, 'w')
			f.write(response.read())

			if self.path not in self.cache:
				self.cache.append(path)
		except IOError as ue:
			print 'Can not write, Wiki folder exceed memory size limit'

def get_information(argv):
	if (len(argv) != 5):
		sys.exit('Usage: %s -p <port> -o <origin>' % argv[0])

	(port_num, origin) = (0, '')
	options, arguments = getopt.getopt(argv[1:], 'p:o:')
	for opt, arg in options:
		if opt == '-p':
			port_num = int(arg)
		elif opt == '-o':
			origin = arg
		else: 
			sys.exit('Usage: %s -p <port> -o <origin>' % argv[0])
	return port_num, origin

def initialize_cache():
		print 'initialize cache here'
		return [1, 2, '/path']

if __name__ == '__main__':
	(port_num, origin) = get_information(sys.argv)

	cache = initialize_cache()

	def handler(*args):
		MyHTTPHandler(cache, origin, *args)

	httpserver = HTTPServer(('', port_num), handler)
	httpserver.serve_forever()

