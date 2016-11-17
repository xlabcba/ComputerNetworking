import argparse
import sys
import socket
import struct
import time

from network import *
from random import randint
from collections import namedtuple, OrderedDict
from util import checksum

# Constants
SYN = 0 + (1 << 1) + (0 << 2) + (0 << 3) + (0 << 4) + (0 << 5)
ACK = 0 + (0 << 1) + (0 << 2) + (0 << 3) + (1 << 4) + (0 << 5)
SYN_ACK = 0 + (1 << 1) + (0 << 2) + (0 << 3) + (1 << 4) + (0 << 5)
FIN = 1 + (0 << 1) + (0 << 2) + (0 << 3) + (0 << 4) + (0 << 5)
FIN_ACK = 1 + (0 << 1) + (0 << 2) + (0 << 3) + (1 << 4) + (0 << 5)
PSH_ACK = 0 + (0 << 1) + (0 << 2) + (1 << 3) + (1 << 4) + (0 << 5)

# TCP header format constant
TCP_HDR_FMT = '!HHLLBBHHH'
# pseudo header format constant used to calculate received TCP checksum
PSH_FMT = '!4s4sBBH'
# store unpacked TCP packet
TCPSeg = namedtuple(
    'TCPSeg', 'tcp_source tcp_dest tcp_seq tcp_ack_seq tcp_check data tcp_flags tcp_adwind')

class Tcp(object):
    def __init__(self, source_ip, destination_ip, destination_components, destination_port):
        self.destination_ip = destination_ip
        self.destination_port = destination_port
        self.source_ip = source_ip
        self.local_port = randint(1001, 65535)
        self.send_buf = ''
        self.recv_buf = ''
        self.tcp_seq = 0
        self.tcp_ack_seq = 0
        self.ip_id = 0
        self.status = ''
        self.adwind_size = 2048
        self.ip = Ip(source_ip, destination_ip)
        self.http_request = ''
        
    def set_request(self, requst_str):
        self.http_request = requst_str

    def pack_tcp_segment(self, payload='', flags=ACK):
        '''
        Generate TCP segment.
        '''
        # TCP header fields
        tcp_source = self.local_port   # source port
        tcp_dest = self.destination_port   # destination port
        tcp_seq = self.tcp_seq
        tcp_ack_seq = self.tcp_ack_seq
        tcp_doff = 5  # 4 bit field, size of tcp header, 5 * 4 = 20 bytes
        tcp_window = self.adwind_size  # maximum allowed window size
        tcp_check = 0
        tcp_urg_ptr = 0
        tcp_offset_res = (tcp_doff << 4) + 0
        tcp_flags = flags
        tcp_header = struct.pack(TCP_HDR_FMT, tcp_source, tcp_dest, tcp_seq,
                                 tcp_ack_seq, tcp_offset_res, tcp_flags,  tcp_window, tcp_check, tcp_urg_ptr)

        # Build pseudo header and calculate checksum
        source_address = socket.inet_aton(self.source_ip)
        dest_address = socket.inet_aton(self.destination_ip)
        placeholder = 0
        protocol = socket.IPPROTO_TCP
        if len(payload) % 2 != 0:
            payload += ' '
        tcp_length = len(tcp_header) + len(payload)
        psh = struct.pack(PSH_FMT, source_address, dest_address, placeholder,
                          protocol, tcp_length)
        psh = psh + tcp_header + payload
        tcp_check = checksum(psh)

        # Pack fields and checksum into TCP header
        tcp_header = struct.pack(TCP_HDR_FMT[:-2], tcp_source, tcp_dest,
                                 tcp_seq, tcp_ack_seq, tcp_offset_res, tcp_flags,  tcp_window) + \
            struct.pack('H', tcp_check) + struct.pack('!H', tcp_urg_ptr)

        return tcp_header + payload

    def unpack_tcp_segment(self, segment):
        '''
        Parse TCP segment
        '''
        # Unpack TCP header
        tcp_header_size = struct.calcsize(TCP_HDR_FMT)
        hdr_fields = struct.unpack(TCP_HDR_FMT, segment[:tcp_header_size])
        tcp_source = hdr_fields[0]
        tcp_dest = hdr_fields[1]
        tcp_seq = hdr_fields[2]
        tcp_ack_seq = hdr_fields[3]
        tcp_doff_resvd = hdr_fields[4]
        tcp_doff = tcp_doff_resvd >> 4  # get the data offset
        tcp_adwind = hdr_fields[6]
        old_tcp_check = hdr_fields[7]
        tcp_urg_ptr = hdr_fields[8]
        tcp_flags = hdr_fields[5]

        # Check if TCP header contains options
        if tcp_doff > 5:
            opts_size = (tcp_doff - 5) * 4
            tcp_header_size += opts_size

        # Get the TCP data
        data = segment[tcp_header_size:]

        # Compute the checksum of the recv packet with psh
        tcp_check = self._tcp_check(segment)

        return TCPSeg(tcp_seq=tcp_seq, 
            tcp_source=tcp_source, 
            tcp_dest=tcp_dest, 
            tcp_ack_seq=tcp_ack_seq,
            tcp_adwind=tcp_adwind,
            tcp_flags=tcp_flags, tcp_check=tcp_check, data=segment[tcp_header_size:])

    def _tcp_check(self, payload):
        '''
        checksum on received TCP packet.
        '''
        # pseudo header fields
        source_address = socket.inet_aton(self.source_ip)
        dest_address = socket.inet_aton(self.destination_ip)
        placeholder = 0
        protocol = socket.IPPROTO_TCP
        tcp_length = len(payload)
	
        # Pack pseudo header and add payload
        psh = struct.pack(PSH_FMT, source_address, dest_address,
                          placeholder, protocol, tcp_length)
        psh = psh + payload

        return checksum(psh)

    def _send(self, data='', flags=ACK):
        '''
        Send packed TCP packets to next layer
        '''
        # Pack TCP segment
        self.send_buf = data
        tcp_segment = self.pack_tcp_segment(data, flags=flags)
        # Send TCP segment to next lower layer
        self.ip.send(tcp_segment)

    def send(self, data):
        '''
        Prepare data and send it to next layer
        '''
        # Loop to send data until receive ACK
        self._send(data, flags=PSH_ACK)
        while not self.recv_ack():
            self._send(data, flags=PSH_ACK)

        # reset send_buf
        self.send_buf = ''

    def _recv(self, size=65535, delay=60):
        '''
        Receive data from next layer
        '''
        # Loop to receive all the data until timeout
        start = time.time()
        while time.time() - start < 60:
            ip_packet_data = self.ip.recv(size, delay)
            if not ip_packet_data:
                continue
            # Unpack received data into TCP segment
            tcp_seg = self.unpack_tcp_segment(ip_packet_data)
            # Check if it is an expected TCP segement
            if tcp_seg.tcp_source != self.destination_port or tcp_seg.tcp_dest != self.local_port or tcp_seg.tcp_check != 0:
                continue
            # If as expected, return the TCP segment
            return tcp_seg
        return None

    def recv(self):
        '''
        Receive all the data from the next layer
        '''
        received_segments = {}
        # Loop to receive all the data
        while True:
            tcp_seg = self._recv()
            if not tcp_seg:
                self.initiates_close_connection()
                sys.exit(1)

            if tcp_seg.tcp_flags & ACK and tcp_seg.tcp_seq not in received_segments:
                received_segments[tcp_seg.tcp_seq] = tcp_seg.data
                self.tcp_ack_seq = tcp_seg.tcp_seq + len(tcp_seg.data)
                # Server wants to close connection
                if tcp_seg.tcp_flags & FIN:
                    self.reply_close_connection()
                    # Transmission is done. Server closes the connection.
                    break
                # If server need to continue to receive
                else:
                    self._send(flags=ACK)

        # Combind list of data into whole piece of data
        sorted_segments = sorted(received_segments.items())
        data = ''.join(v[1] for v in sorted_segments)

        return data

    def recv_ack(self, offset=0):
        '''
        Receive ACK
        '''
        # Loop to receive ACK until timeout
        start_time = time.time()
        while time.time() - start_time < 60:
            tcp_seg = self._recv(delay=60)
            if not tcp_seg:
                break
            if tcp_seg.tcp_flags & ACK and tcp_seg.tcp_ack_seq >= self.tcp_seq + len(self.send_buf) + offset:
                self.tcp_seq = tcp_seg.tcp_ack_seq
                self.tcp_ack_seq = tcp_seg.tcp_seq + offset
                return True

        return False

    def initiates_close_connection(self):
        '''
        Initiates Connection to Close
        '''
        self._send(flags=FIN_ACK)
        self.recv_ack(offset=1)

        tcp_seg = self._recv()

        if not tcp_seg or not (tcp_seg.tcp_flags & FIN):
            print "Close connection failed"
            self.initiates_close_connection()
            sys.exit(1)

        self._send(flags=ACK)
        self.ip.close_all()

    def reply_close_connection(self):
        '''
        Close Connections
        '''
        self.tcp_ack_seq += 1
        self._send(flags=FIN_ACK)
        tcp_seg = self.recv_ack(offset=1)
        self.ip.close_all()

    def three_way_hand_shake(self):
        '''
        Do three way handshake
        '''
        self.tcp_seq = randint(0, (2 << 31) - 1)

        self._send(flags=SYN)
        if not self.recv_ack(offset=1):
            print 'connect failed'
            self.initiates_close_connection()
            sys.exit(1)

        self._send(flags=ACK)

    def download(self):
        '''
        Download all the data
        '''
        self.send(self.http_request)

        data = self.recv()
        if not data.startswith("HTTP/1.1 200 OK"):
            self.initiates_close_connection()
            sys.exit(1)

        return data
