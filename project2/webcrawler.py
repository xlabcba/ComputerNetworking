#!/usr/bin/python
import socket
import sys
import re
import select

# Maximum size to read from socket
PAGE_SIZE = 4096
# Number of processes
WORKER_NUMBER = 100
# Possible status of returned page
STATUS_OK = '200'
STATUS_REDIRECT = '301'
STATUS_FOUND = '302'
STATUS_FORBIDDEN = '403'
STATUS_NOT_FOUND = '404'
STATUS_INTERNAL_SERVER_ERROR = '500'
# Status group according to needed operation
STATUS_SUCCESS = [STATUS_OK]
STATUS_REDIRECTION = [STATUS_REDIRECT, STATUS_FOUND]
STATUS_CLIENT_ERROR = [STATUS_FORBIDDEN, STATUS_NOT_FOUND]
STATUS_SERVER_ERROR = [STATUS_INTERNAL_SERVER_ERROR]

class Worker(object):
    """
    Each worker wraps a socket.
    The state of worker can be:
    0 - write mode ; 1 - read mode; -1 - error mode;
    Worker runs in following mechanism:
    1. Initialized in write mode, and wait for writing job from Master Crawler.
    2. Assigned writing job from Master Crawler, and keep working on it.
    3. After finish writing, switch to read mode to read the response page.
    4. After finish reading, analyze the response, and return result to Master Crawler.
    5. Reset to initial state and repeat step 1.
    """
    # Initialize worker
    def __init__(self, host, port, i):
        self.host = host
        self.port = port
        self.state = 0
        self.write_buffer = ''
        self.read_buffer = ''
        self.target_url = ''
        self.socket = None
        self.init_socket()
        self.no = i

    # Initialize socket
    def init_socket(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.setblocking(False)
        except Exception as e:
            state = -1

    # Reset worker to be reused
    def try_reset_worker(self):
        try:
            self.state = 0
            self.read_buffer = ''
            self.write_buffer = ''
            self.target_url
            self.socket.shutdown(2)
            self.socket.close()
            self.init_socket()
        except Exception as e:
            self.state = -1

    # Do read task
    def read(self):
        try:
            resp = self.socket.recv(PAGE_SIZE)
            if resp != 0: self.read_buffer += resp
            # Read is finished
            if resp == 0 or resp == '' or \
               self.read_buffer.endswith('\r\n\r\n') or \
               self.read_buffer.endswith('</html>'):
                # Process read page
                return self.process_response(self.read_buffer)
        except Exception as e:
            # If failed to read, reset worker, and
            # add target_url back to to_visit
            self.try_reset_worker()
            return set(), set(self.target_url), set()
        return set(), set(), set()

    # Do write task
    def write(self, target_url, buffer):
        # Check if the worker is idle to be assigned a new task
        if not self.write_buffer:
            # Check if no task to do at this moment
            if not target_url and not buffer: return
            # Assign new task to current idle worker
            self.write_buffer = buffer
            self.target_url = target_url
        try:
            n = self.socket.send(self.write_buffer)
            self.write_buffer = self.write_buffer[n:]
            # Write is finished
            if not self.write_buffer:
                self.state = 1
                self.write_buffer = ''
            return ''
        except Exception as e:
            # If failed to read, reset worker, and
            # add target_url back to to_visit
            self.try_reset_worker()
            return self.target_url

    # Analyze read page
    def process_response(self, resp):
        flags, to_visit, visited = set(), set(), set()

        status_code = self.get_status_code(resp)
        if status_code in STATUS_SUCCESS:
            flags = self.find_flags(resp)
            to_visit = self.find_out_links(resp)
            visited.add(self.target_url)
        elif status_code in STATUS_REDIRECTION:
            to_visit = self.find_redirect_location(resp)
            visited.add(self.target_url)
        elif status_code in STATUS_CLIENT_ERROR:
            visited.add(self.target_url)
        elif status_code in STATUS_SERVER_ERROR:
            to_visit.add(self.target_url)

        # Reconnect, so we can use this socket again
        self.try_reset_worker()

        return flags, to_visit, visited

    # Find flags in read page
    def find_flags(self, resp):
        return set(re.findall("FLAG: (.{64})", resp))

    # Find hyperlinks to visit in read page
    def find_out_links(self, resp):
        return set(re.findall("<a href=\"(.*?)\">[^<]*</a>", resp))

    # Find locations to visit in read page
    def find_redirect_location(self, resp):
        return set(re.findall("Location: (.*?)\r\n", resp))

    # Find status code of read page
    def get_status_code(self, resp):
        status_code = re.findall("HTTP/1.1 (.*?) ", resp)
        return status_code[0] if status_code else ''

    # Necessary to operate socket
    def fileno(self):
        return self.socket.fileno()

class MasterCrawler:
    """
    Master Crawler is the main port of crawling.
    It works as following:
    1. Tries to login fakebook account, and records the cookies
       for the following requests, and first location to visit.
    2. Executes as an asynchronous process, which efficiently select
       readable and writable worker list. Assign new task to empty
       workers.
    3. Maintains a set of found flags, a set as stack of url paths to
       visit, and a set of url paths which have been visited. After each
       worker returns found flags, to-visit paths and visited path, Master
       Crawler merges the result into these three corresponding list.
    4. Finishes the process and return when 5 flags have all been found.
    """
    # Initialize Master Crawler
    def __init__(self):
        self.cookies = ''
        self.flags = set()
        self.to_visit = set()
        self.visited = set()
        self.workers = []

    # Do asynchronous crawling process
    def startCrawling(self, host):
        crawl_request = "GET {url} HTTP/1.1\r\n" + \
                "Host: " + host + "\r\n" + \
                "Cookie: " + self.cookies + "\r\n" + \
                "Connection: keep-alive" + "\r\n\r\n"
        while len(self.flags) < 5:
            rlist = [worker for worker in self.workers if worker.state == 1]
            wlist = [worker for worker in self.workers if worker.state == 0]

            readables, writables, exceptions = select.select(rlist, wlist, [], 3)

            if readables: self.process_read(readables)
            if writables: self.process_write(writables, crawl_request)

    # Iterate readable workers
    def process_read(self, readables):
        for worker in readables:
            flags, to_visit, visited = worker.read()
            # Print new flags if found
            new_flags = flags - self.flags
            for flag in new_flags: print flag
            # Update flags
            self.flags |= flags
            # Update to_visit paths
            for url in to_visit:
                # Add url path if it hasn't been visited
                # and belongs to the required domain
                if url not in self.visited and '/fakebook/' in url:
                    self.to_visit.add(url)
            # Update visited paths
            self.visited |= visited

    # Iterate writable workers
    def process_write(self, writables, crawl_request):
        for worker in writables:
            target_url, request = '', ''
            # Start a new worker writing task, if write buffer is empty
            if not worker.write_buffer and len(self.to_visit) > 0:
                target_url = self.to_visit.pop()
                request = crawl_request.format(url = target_url)
            # If worker failed to write, add the target url back into to_visit
            to_visit = worker.write(target_url, request)
            if to_visit: self.to_visit.add(to_visit)

    # Do login process
    def login(self, host, port, username, password):
        counter = 10
        while counter > 0:
            resp = self.getLoginPage(host, port)
            status_code = self.get_status_code(resp)
            if status_code != STATUS_OK:
                print "get login page: \n"
                print resp
                counter -= 1
                continue

            resp = self.postFakebookLogin(host, port, username, password, resp)
            status_code = self.get_status_code(resp)
            if status_code != STATUS_FOUND:
                counter -= 1
                print "post to login: \n"
                print resp
                continue

            self.cookies = self.parseCookies(resp)
            self.to_visit |= self.findFirstLocation(resp)
            self.workers = [Worker(host, port, i) for i in range(WORKER_NUMBER)]
            break
        return counter > 0

    # First GET to get login page
    def getLoginPage(self, host, port):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        # url can also be /accounts/login/?next=/fakebook
        # if without the /?next=/fakebook, it will be redirectly automatically
        # This is the GET request that goes to the login page
        get_fakebook_login_page = "GET /accounts/login/ HTTP/1.1\r\n" + \
                                  "Host: " + host + "\r\n\r\n"
        s.send(get_fakebook_login_page)
        # While loop to read all data
        resp_lst = []
        while True:
            curr = s.recv(PAGE_SIZE)
            if curr == 0 or curr == '': break
            resp_lst.append(curr)
        s.shutdown(2)
        s.close
        return ''.join(resp_lst)

    # First POST to login into account
    def postFakebookLogin(self, host, port, username, password, resp):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        # Parse out the csrftoken and sessionid
        csrftoken = re.findall('csrftoken=(\w*)', resp)[0]
        sessionid = re.findall('sessionid=(\w*)', resp)[0]

        # This is the POST request that logins in the Fakebook homepage
        login_request = "POST /accounts/login/ HTTP/1.1\r\n" + \
                        "Host: {host}\r\n" + \
                        "Content-Length: {length}\r\n" + \
                        "Cookie: csrftoken={csrftoken}; sessionid={sid}\r\n\r\n"
        formdata = "username={username}&password={password}&csrfmiddlewaretoken={csrf}&next=/fakebook/"\
                    .format(username=username, password=password, csrf=csrftoken)
        login_request = login_request.format(host=host, length=len(formdata), csrftoken=csrftoken, sid=sessionid)
        s.send(login_request+formdata)
        # While loop to read all data
        resp_lst = []
        while True:
            curr = s.recv(PAGE_SIZE)
            if curr == 0 or curr == '': break
            resp_lst.append(curr)
        s.shutdown(2)
        s.close()
        return ''.join(resp_lst)

    # Find cookies to be used in following crawling
    def parseCookies(self, resp):
        # Creates a dictionary that records down the keys and values of cookies
        cookies_list = []
        cookies = re.findall('Set-Cookie: [^=]*=(.*?);',resp)
        keys = re.findall('Set-Cookie: (.*?)=',resp)
        for key, cookie in zip(keys, cookies):
            cookies_list.append(key + '=' + cookie)
        cookies = '; '.join(cookies_list)
        return cookies

    # Find first location to visit
    def findFirstLocation(self, resp):
        # In the response, there is a line: Location: http://cs5700f16.ccs.neu.edu/fakebook/
        return set(re.findall('Location: (https?:\/\/(?:www\.|(?!www))[^\s\.]+\.[^\s]{2,}|www\.[^\s]+\.[^\s]{2,})', resp))

    # Find status code of page
    def get_status_code(self, resp):
        status_code = re.findall("HTTP/1.1 (.*?) ", resp)
        return status_code[0] if status_code else ''

# Parse system argument
def read_arguments():
    if len(sys.argv) != 3:
        print "Invalid Command"
        sys.exit()
    username, password = sys.argv[1], sys.argv[2]
    return username, password

if __name__ == '__main__':
    host = "cs5700f16.ccs.neu.edu"
    port = 80
    username, password = read_arguments()
    crawler = MasterCrawler()
    if not crawler.login(host, port, username, password):
        print "Error login"
        sys.exit()
    crawler.startCrawling(host)
