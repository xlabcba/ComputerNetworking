import sys
import socket
from urlparse import urlparse
from application import *

def get_destination_components_ip(url):
    components = urlparse(url)

    try:
        # If the url does not have http:// in front, we will add it
        if not components.scheme:
            url = 'http://' + url
            components = urlparse(url)

        # Raw socket only handles http
        if components.scheme != 'http':
            print 'Only HTTP is supported in this raw socket'
            sys.exit(1)

        # Get destination IP
        destination_ip = socket.gethostbyname(components.netloc)
        return components, destination_ip
    except Exception, e:
        print e, "Program exit."
        sys.exit(1)

def get_source_ip():
    try:
        # Get source IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("www.google.com",80))
        source_ip = s.getsockname()[0]
        s.close()
        return source_ip
    except Exception, e:
        print e, "Program exit."
        sys.exit(1)

def get_filename(path):
    print path.split('/')
    return path.split('/')[-1] or 'index.html'

def save_to_file(data, filename):
    with open(filename, "w+") as f:
        f.write(data)

if __name__ == '__main__':
    # Parse arguments
    if len(sys.argv) != 2:
        sys.exit('There should be 2 arguments: ./rawhttpget [url]')
    url = sys.argv[1]
    destination_components, destination_ip = get_destination_components_ip(url)
    source_ip = get_source_ip()
    filename = get_filename(destination_components.path)

    # Call application layer
    http = Http(source_ip, destination_ip, destination_components)
    data = http.start()

    # Save result to file
    save_to_file(data, filename)
