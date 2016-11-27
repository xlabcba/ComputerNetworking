# Execution Instruction for localhost:
1. HTTP Server:
If httpserver is not an executable file, do chmod +x httpserver
./httpserver -p <port> -o <url> [e.g. port = 51111, url = www.wikipedia.org]
wget http://localhost:<port><path> [e.g. port = 51111, path = /wiki/science]
2. DNS Server:
If dnsserver is not an executable file, do chmod +x httpserver
./dnsserver -p <port> -n <name> [e.g. port = 50000, name = cs5700cdn.example.com (can be anything)]
dig @localhost <name> -p <port> [e.g. name = cs5700cdn.example.com, port = 50000]


# High-Level Approach
1. Http Server
We applied the BaseHTTPServer library in Python to do corresponding job for the GET request from the client,
 and return the information downloaded from the original server to the client. LRU cache method was applied to enhance
 the performance, as the storage was assume to be limited relative to the size of the information we are requested to
 download.

2. DNS Server
We implemented the receiving and sending DNS packet by using socketServer. We also implemented the function of packing
 and unpacking DNS packet.

# Performance Enhancement Approaches
1. Cache Management
As we have the assumption that the replica server will have limited disk quota, thus it is necessary to implement an
 effective cache management strategy to cache the downloaded materials. We applied the LRU(Least Recently Used)
 strategy, in which the least recently used item will be discarded firstly.

# Challenges
1. We spent a lot of time on exploring the big picture of the whole project, such as the working mechanism of the Http
 Server and DNS Server.
2. The cache management method is a big and important decision for us. For now, we use the LRU cache method, however,
 for the future work, we are going to compare the LRU and LFU cache method respectively and utilize the one with better
 performance.