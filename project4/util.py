import socket
import array

def checksum(s):
    if len(s) & 1:
    	s = s + '\0'
    words = array.array('H', s)
    sum = 0
    for word in words:
    	sum = sum + word
        hi = sum >> 16
        lo = sum & 0xffff
        sum = hi + lo
    # sum = sum + (sum >> 16)
    return (~sum) & 0xffff