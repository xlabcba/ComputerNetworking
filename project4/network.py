import argparse
import sys
import socket
import struct
import time
import socket

from datalink import *
from random import randint
from collections import namedtuple, OrderedDict
from util import checksum

# IP header format constant
IP_HDR_FMT = '!BBHHHBBH4s4s'
# store unpacked IP packet
IPPacket = namedtuple(
    'IPPacket', 'ip_tlen ip_id ip_frag_off ip_saddr ip_daddr data ip_check ip_protocol')

class Ip(object):
    def __init__(self, source_ip, destination_ip):
        self.source_ip = source_ip
        self.destination_ip = destination_ip
	self.sock = Datalink(self.source_ip)

    def pack_ip_packet(self, payload):
        '''
        Generate IP datagram.
        `payload` is TCP segment
        '''
        # Set fields in IP packet
        ip_tos = 0
        ip_tot_len = 20 + len(payload)
        ip_id = randint(0, 65535)
        ip_frag_off = 0
        ip_ttl = 255
        ip_proto = socket.IPPROTO_TCP
        ip_check = 0
        ip_saddr = socket.inet_aton(self.source_ip)
        ip_daddr = socket.inet_aton(self.destination_ip)

        # Build ip_header to calculate checksum
        ip_ihl_ver = (4 << 4) + 5
        ip_header = struct.pack(IP_HDR_FMT, ip_ihl_ver, ip_tos, ip_tot_len,
                                ip_id, ip_frag_off, ip_ttl, ip_proto, ip_check, ip_saddr, ip_daddr)
        ip_check = checksum(ip_header)

        # Pack fields and checksum into IP packet header
        ip_header = struct.pack('!BBHHHBB', ip_ihl_ver, ip_tos, ip_tot_len,
                                ip_id, ip_frag_off, ip_ttl, ip_proto) + \
                                struct.pack('H', ip_check) + struct.pack('!4s4s', ip_saddr, ip_daddr)

        return ip_header + payload


    def unpack_ip_packet(self, datagram):
        '''
        Parse IP datagram
        '''
        # Unpack IP packet
        hdr_fields = struct.unpack(IP_HDR_FMT, datagram[:20])
        ip_header_size = struct.calcsize(IP_HDR_FMT)
        ip_ver_ihl = hdr_fields[0]
        ip_ihl = ip_ver_ihl - (4 << 4)

        # Check if there is options fields in header
        if ip_ihl > 5:
            opts_size = (ip_ihl - 5) * 4
            ip_header_size += opts_size

        # Get the IP header, payload, and checksum
        ip_headers = datagram[:ip_header_size]
        data = datagram[ip_header_size:hdr_fields[2]]
        ip_check = checksum(ip_headers)

        return IPPacket(ip_daddr=socket.inet_ntoa(hdr_fields[-1]),
            ip_saddr=socket.inet_ntoa(hdr_fields[-2]),
            ip_protocol=hdr_fields[6],
            ip_frag_off=hdr_fields[4],
            ip_id=hdr_fields[3], 
            ip_tlen=hdr_fields[2], 
            ip_check=ip_check, data=data)

    def send(self, tcp_segment):
        '''
        Pack TCP Segment into IP packet and Send to Next Layer
        '''
        # Pack TCP Segment into IP Packet
        ip_packet = self.pack_ip_packet(tcp_segment)
        # Send IP Packet to Next Lower Layer
	try:
            self.sock.send(ip_packet)
	except Exception as e:
            raise


    def recv(self, size, delay):
        '''
        Receive IP Packet from Next Layer and Unpack to TCP Segment
        '''
        # Loop to receive packet
	while True:
            data = self.sock.receive()
            # Unpack received packet into IP Packet
            ip_packet = self.unpack_ip_packet(data)
            # Check if the IP packet is one expected packet
            if ip_packet.ip_daddr != self.source_ip or ip_packet.ip_check != 0 or ip_packet.ip_saddr != self.destination_ip or ip_packet.ip_protocol != socket.IPPROTO_TCP:
                continue
            # If so, send the TCP segment into upper layer
            return ip_packet.data    

    def close_all(self):
        '''
        Close sockets
        '''
	self.sock.close_all()
