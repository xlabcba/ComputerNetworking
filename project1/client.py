#!/usr/bin/python
import socket
import sys
import ssl

soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
TERM = 'cs5700fall2016'

def read_arguments():
    argc = len(sys.argv)
    if argc < 3 or argc > 6:
        print "Invalid input"
        sys.exit()
    ssl_flag = False
    port = 27993
    if '-s' in sys.argv:
        ssl_flag = True
        port = 27994
    if '-p' in sys.argv:
        port = int(sys.argv[sys.argv.index('-p') + 1])
    hostname = sys.argv[-2]
    nuid = sys.argv[-1]
    HELLO_MESSAGE = TERM + ' HELLO ' + nuid + '\n'
    return nuid, hostname, port, ssl_flag, HELLO_MESSAGE

def get_solution(msg_recv):
    return int(eval(''.join(msg_recv.split()[2:])))

def check_status(msg_recv):
    msg = msg_recv.split()
    return len(msg) == 5 and \
            msg[0] == TERM and \
            msg[1] == 'STATUS' and \
            msg[2].isdigit() and \
            msg[3] in ('+', '-', '*', '/') and \
            msg[4].isdigit()

def check_result(msg_recv):
    msg = msg_recv.split()
    return len(msg) == 3 and \
            msg[0] == TERM and \
            len(msg[1]) == 64 and \
            msg[2] == 'BYE'

def normal_socket():
    soc.connect((hostname, port))
    soc.send(HELLO_MESSAGE)
    msg_recv = soc.recv(256)
    while check_status(msg_recv):
        solution = get_solution(msg_recv)
        solution_msg = TERM + " " + str(solution) + "\n"
        soc.send(solution_msg)
        msg_recv = soc.recv(256)
    if check_result(msg_recv):
        return msg_recv.split()[1]
    else:
        print "Invalid received message"
        soc.close()
        sys.exit()

def ssl_socket():
    simple_ssl = ssl.wrap_socket(soc, cert_reqs = ssl.CERT_NONE)
    simple_ssl.connect((hostname,port))
    simple_ssl.write(HELLO_MESSAGE)
    msg_recv = simple_ssl.recv(256)
    while check_status(msg_recv):
        solution = get_solution(msg_recv)
        solution_msg = TERM + " " + str(solution) + "\n"
        simple_ssl.write(solution_msg)        
        msg_recv = simple_ssl.recv(256)
    if check_result(msg_recv):
        return msg_recv.split()[1]
    else: 
        print "Invalid received message"
        soc.close()
        sys.exit()
    
nuid, hostname, port, ssl_flag, HELLO_MESSAGE = read_arguments()
if ssl_flag:
    print ssl_socket()
else:
    print normal_socket()
