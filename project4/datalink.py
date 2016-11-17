import socket
import sys
import binascii
import struct
import commands
import subprocess
import re
import traceback
from collections import namedtuple

# Constants
ETHER_DEST_MAC_ADDR = 'FFFFFFFFFFFF'
ARP_RECV_HW_ADDR = '000000000000'
PAGE_SIZE = 4096
# the default ethernet interface is eth0
NET_INTERFACE = 'eno16777736'
# arp format constant
ARP_FORMAT = '!HHBBH6s4s6s4s'
# store disassembled ARP Packet
ARPSeg = namedtuple(
    'ARPSeg', 'hw_type proto_type hw_addr_len proto_addr_len op send_hw_addr recv_hw_addr send_proto_addr recv_proto_addr')
# ether format constant
ETHER_FORMAT = '!6s6sH'
# store disassembled ETHER Packet
ETHERSeg = namedtuple(
    'ETHERSeg', 'dest_mac_addr src_mac_addr ethernet_type data')

# DataLink layer
class Datalink:
    def __init__(self, source_ip):
        self.src_mac = ""
        self.dest_mac = ""
        self.gateway_mac = ""
	self.source_ip = source_ip
        # initiate a sending and a receiving raw sockets
        self.send_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        self.recv_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800))

    def assemble_ether_packet(self, src_mac_addr, dest_mac_addr, data, ether_type=0x800):
        '''
        Build Ethernet Packet
        '''
        src = binascii.unhexlify(src_mac_addr)
        dest = binascii.unhexlify(dest_mac_addr)
        header = struct.pack(ETHER_FORMAT, dest, src, ether_type)
        return header + data

    def disassemble_ether_packet(self, ether_packet):
        '''
        Disassemble packet into Ethernet Segment
        '''
        # Unpack Ethernet header
        [dest_mac_addr, src_mac_addr, ethernet_type] = struct.unpack(ETHER_FORMAT, ether_packet[:14])
        dest_mac_addr = binascii.hexlify(dest_mac_addr)
        src_mac_addr = binascii.hexlify(src_mac_addr)

        # Get the payload of the packet
        data = ether_packet[14:]

        return ETHERSeg(dest_mac_addr=dest_mac_addr, src_mac_addr=src_mac_addr, ethernet_type=ethernet_type, data=data)

    def assemble_arp_packet(self, send_hw_addr, send_proto_addr, recv_hw_addr, recv_proto_addr):
        '''
        Build ARP Packet
        '''
	# type of hardware, 1 for ethernet
        hw_type = 1
        # type of protocol, default is ip
        proto_type = 0x800
        # length of hardware address
        hw_addr_len = 6
        # length of ip address
        proto_addr_len = 4
        # operation: 1 for request, 2 for reply
        operation = 1

        # convert MAC address and IP address to binary format
        bin_SHA = binascii.unhexlify(send_hw_addr)
        bin_RHA = binascii.unhexlify(recv_hw_addr)
        bin_SPA = socket.inet_aton(send_proto_addr)
        bin_RPA = socket.inet_aton(recv_proto_addr)

        return struct.pack(ARP_FORMAT, hw_type, proto_type, hw_addr_len, proto_addr_len, \
                 operation, bin_SHA, bin_SPA, bin_RHA, bin_RPA)

    def disassemble_arp_packet(self, arp_packet):
        '''
        Disassemble Packet into ARP Segment
        '''
        # Unpack ARP packet
        [hw_type, proto_type, hw_addr_len, proto_addr_len, op, bin_SHA, bin_SPA, \
        bin_RHA, bin_RPA] = struct.unpack(ARP_FORMAT, arp_packet)

        # Parse the hardware and protocol address
        send_hw_addr = binascii.hexlify(bin_SHA)
        recv_hw_addr = binascii.hexlify(bin_RHA)
        send_proto_addr = socket.inet_ntoa(bin_SPA)
        recv_proto_addr = socket.inet_ntoa(bin_RPA)

	return ARPSeg(hw_type=hw_type,
		proto_type=proto_type,
		hw_addr_len=hw_addr_len,
		proto_addr_len=proto_addr_len,
		op=op,
		send_hw_addr=send_hw_addr,
		recv_hw_addr=recv_hw_addr,
		send_proto_addr=send_proto_addr,
		recv_proto_addr=recv_proto_addr)

    def connect(self):
        '''
        Build Connection
        '''
        # connect the sender and receiver
        self.send_sock.bind((NET_INTERFACE, 0))

    def get_gtwy_mac_addr(self, dest_ip):
        '''
        Get Gateway MAC Address by ARP
        '''
        # build raw socket
        temp_send_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
        temp_recv_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0806))

        # get the ip and mac addresses
        src_ip = self.source_ip
        src_mac = self.get_src_mac_addr(NET_INTERFACE)
        self.src_mac = src_mac

        # Build an ARP packet to do broadcast
        arp_req_pkt = self.assemble_arp_packet(src_mac, src_ip, ARP_RECV_HW_ADDR, dest_ip)

        # Build an Ethernet packet based on the ARP packet
        ether_req_pkt = self.assemble_ether_packet(src_mac, ETHER_DEST_MAC_ADDR, arp_req_pkt, 0x0806)

        # Send packet to get Destination MAC Address
        temp_send_sock.sendto(ether_req_pkt, (NET_INTERFACE, 0))

        # Loop to parse data from received raw packets
        while True:
            # Get raw data
            raw_pkt = temp_recv_sock.recvfrom(PAGE_SIZE)[0]
            # Disassemble the raw pkt received into Ethernet packet
            ether_pkt = self.disassemble_ether_packet(raw_pkt)
            # Check is Ethernet packet is sent to current mac
            if self.src_mac == ether_pkt.dest_mac_addr:
                # Disassemble the header into ARP packet
                arp_res_pkt = self.disassemble_arp_packet(ether_pkt.data[:28])
                # Check if ARP packet is one expected sent to current address
                if arp_res_pkt.recv_proto_addr == src_ip and arp_res_pkt.send_proto_addr == dest_ip:
                    break

        # Close the temp sockets
        temp_send_sock.close()
        temp_recv_sock.close()

        # Found the address and return
        return arp_res_pkt.send_hw_addr

    def get_gateway_ip(self):
        '''
        Get Gateway IP Address
        '''
        # Get the gateway ip of local machine
        output = subprocess.check_output(['route', '-n']).split('\n')
        data, res = [], []

        # Loop to find the line with the gateway ip
        for line in output:
            if line[:7] == '0.0.0.0':
                data = line.split(' ')
                break
        # Filter out empty item
        res = [d for d in data if d != '']

        # res[1] is the ip of gateway of the local machine
        return res[1]

    def get_src_mac_addr(self, interface = NET_INTERFACE):
        '''
        Get Source MAC Address
        '''
        # Get the mac address of the local machine
        ip_config = commands.getoutput("/sbin/ifconfig")

        # Get the mac address in the ifconfig info
        mac_addresses = re.findall("HWaddr (.*?) ", ip_config)
        print 'mac_addresses: ', mac_addresses

        # remove all the ':' in the result
        return mac_addresses[1].replace(":", "")

    def send(self, raw_packet):
        '''
        Build Ethernet Packet and Send Out to Destination
        '''
        # Build connection
        self.connect()

        # Get the gateway mac address
        if self.gateway_mac == '':
            try:
                self.gateway_mac = self.get_gtwy_mac_addr(self.get_gateway_ip())
            except:
                print 'ARP Fails, can not find mac address'

        # Set the dest mac address as the mac address of gateway
        self.dest_mac = self.gateway_mac
        # Build Ethernet packet
        pkt = self.assemble_ether_packet(self.src_mac, self.gateway_mac, raw_packet)
        # Send the Ethernet packet out to the destination
        self.send_sock.send(pkt)

        print 'success send'

    def receive(self):
        '''
        Receive Packet to Disassemble and Send to Upper Layer
        '''
        # Loop to keep receiving, until received all
        while True:
            # Get the data in size of one page size by raw socket
            try:
                packet_recv = self.recv_sock.recvfrom(PAGE_SIZE)[0]
            except socket.error:
                print 'raw socket recv wrong'

            # Disassemble the packet received
            pkt = self.disassemble_ether_packet(packet_recv)

            # Check if the packet is the one expected
            if pkt.dest_mac_addr == self.src_mac and pkt.src_mac_addr == self.dest_mac:
                print 'success receive'
                return pkt.data

    def close_all(self):
    	self.send_sock.close()
    	self.recv_sock.close()
