# Socket Basics

## High Level Approach:

We basically establish a socket, depending on whether it is an SSL connection, if it is an SSL connection, we wrap the socket, and then make a connection to the host name and port; otherwise if it is a normal connection, we make a connection to the host name and port directly. After that, we parse the message returned from the socket and print out the secret flags. In the end, we close the socket.

## Challenge:

We initially wrote our code in C, we used "sudo apt-get install libssl-dev" to install the openssl on our linux machine, compiled our code without any problems. But we could not get it running on the CCIS machine because "libssl.so.1.0.0" is not installed on there. So, we switched to Python.

## Code Testing:

We manually tested all the cases.

Makefile is used to build the client.c version.
Remove the extension of client.py to make it an executable for the python version