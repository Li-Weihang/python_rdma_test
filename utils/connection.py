import socket
import time
# All supported types should be imported here for the parser of received message
# or the Global() method can't get objects' type from the received string
from builtins import str, int
from pyverbs.addr import GID

from pyverbs.cm_enums import *
from pyverbs.cmid import CMID, AddrInfo
from pyverbs.qp import QPInitAttr, QPCap

RESERVED_LEN = 20  # We should reserve some space for receiving because the length of exchanged strings may be not equal
HANDSHAKE_WORDS = "Aloha!"


class CommError(Exception):
    def __init__(self, message):
        self.message = message
        super(CommError, self).__init__(message)

    def __str__(self):
        return self.message


class CommBase:
    def __init__(self):
        pass

    @staticmethod
    def prepare_send_msg(**kwargs):
        if not bool(kwargs):
            send_msg = HANDSHAKE_WORDS
        else:
            print("-- Local Info")
            # Prepare the info to be sent
            send_msg = ""
            for key, value in kwargs.items():
                print(key, ":", value)
                send_msg = send_msg + key + ':' + type(value).__name__ + ':' + str(value) + ','

            send_msg = send_msg[:-1]
            print('-' * 80)

        return send_msg

    @staticmethod
    def parse_recv_msg(only_handshake, recv_msg):
        if only_handshake:
            try:
                if recv_msg != HANDSHAKE_WORDS:
                    raise CommError("Failed to handshake with remote peer by " + CommBase.__class__.__name__)
            except CommError as e:
                print(e)
        else:
            # Parse the recv info, create objects in specified type and organize them into a dictionary
            key_value = {}
            print("-- Remote Info")
            for item in recv_msg.split(','):
                key, value_type, value = item.split(':', 2)
                key_value[key.strip()] = globals()[value_type.strip()](value.strip())
                print(key, ":", value)
            print('-' * 80)

            return key_value


# TODO: Error Handling/Handshake Overtime
class SKT(CommBase):
    def __init__(self, port, ip=None):
        """
        Initializes a Socket object for RDMA test, the process of socket connection has
        been encapsulated in this constructor
            :param port: The port number for TCP/IP socket
            :param ip: The ip address of the server, only the client needs this param
        """
        super(CommBase, self).__init__()
        self.socket = socket.socket()
        # Avoid the "Address already in use" error
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.isServer = False

        if ip is None:  # is Server
            self.isServer = True
            self.socket.bind(('0.0.0.0', port))  # All IP can be accepted.
            self.socket.listen()
            self.client, self.addr = self.socket.accept()
            self.socket.close()  # We only support single client, no more clients will be accepted
            self.socket = self.client
        else:
            self.socket.connect((ip, port))

    def handshake(self, **kwargs):
        """
        Makes a handshake between the server and client. The users can exchange anything the want with the remote peer.
        For example:
            1. socket.handshake()
                This exchanges nothing, which is always used as a synchronization mechanism.
            2. socket.handshake(qpn = xx, psn = yy)
                This exchanges qpn and psn with remote peer, this can be used before INIT->RTR.
            3. socket.handshake(str = "hello bro")
                This exchanges a message between server and client.
        :param kwargs: Users should pass args in the form of 'key1 = value1, key2 = value2 ...', and both ends should
            provide same keys.
        :return: A dictionary based on received info if any param is passed in, or nothing.
        """
        just_handshake = not bool(kwargs)

        send_msg = self.prepare_send_msg(**kwargs)

        self.socket.send(send_msg.encode('utf-8'))

        recv_msg = self.socket.recv(len(send_msg) + RESERVED_LEN).decode('utf-8')

        time.sleep(0.5) # wait for a while in case that the program can't spilt message between handshakes.

        return self.parse_recv_msg(just_handshake, recv_msg)

    def close(self):
        if not self.isServer:
            self.socket.close()

    def __del__(self):
        self.socket.close()


# TODO: Error Handling
class CM(CommBase):
    def __init__(self, port, ip=None):
        """
        Initializes a CMID object for RDMA test, the process of creating CM connection has
        been encapsulated in this constructor
            :param port: The port number for TCP/IP socket
            :param ip: The ip address of the server, only the client needs this param
        """
        super(CommBase, self).__init__()
        cap = QPCap(max_recv_wr=1)
        qp_init_attr = QPInitAttr(cap=cap)
        self.isServer = False

        # TODO: Create a QP after connection instead of creating one each time user want to handshake

        if ip is None:
            self.isServer = True
            cai = AddrInfo(src='0.0.0.0', src_service=str(port), port_space=RDMA_PS_TCP, flags=RAI_PASSIVE)
            self.cmid = CMID(creator=cai, qp_init_attr=qp_init_attr)
            self.cmid.listen()
            client_cmid = self.cmid.get_request()
            client_cmid.accept()
            self.cmid.close()  # # We only support single client, no more clients will be accepted
            self.cmid = client_cmid
        else:
            cai = AddrInfo(src='0.0.0.0', dst=ip, dst_service=str(port), port_space=RDMA_PS_TCP, flags=0)
            self.cmid = CMID(creator=cai, qp_init_attr=qp_init_attr)
            self.cmid.connect()

    def handshake(self, **kwargs):
        """
        Makes a handshake between the server and client. The users can exchange anything the want with the remote peer.
        For example:
            1. socket.handshake()
                This exchanges nothing, which is always used as a synchronization mechanism.
            2. socket.handshake(qpn = xx, psn = yy)
                This exchanges qpn and psn with remote peer, this can be used before INIT->RTR.
            3. socket.handshake(str = "hello bro")
                This exchanges a message between server and client.
        :param kwargs: Users should pass args in the form of 'key1 = value1, key2 = value2 ...', and both ends should
            provide same keys.
        :return: A dictionary based on received info if any param is passed in, or nothing.
        """
        just_handshake = not bool(kwargs)

        send_msg = self.prepare_send_msg(**kwargs)
        size = len(send_msg)

        # Recv Message
        recv_mr = self.cmid.reg_msgs(size + RESERVED_LEN)
        self.cmid.post_recv(recv_mr, size)

        # Send Message
        send_mr = self.cmid.reg_msgs(size)
        send_mr.write(send_msg.encode('utf-8'), size)
        self.cmid.post_send(send_mr, 0, size)

        recv_wc = self.cmid.get_recv_comp()
        send_wc = self.cmid.get_send_comp()

        recv_msg = recv_mr.read(recv_wc.byte_len, 0).decode('utf-8')
        # print(recv_msg)

        return self.parse_recv_msg(just_handshake, recv_msg)

    def close(self):
        if not self.isServer:
            self.cmid.close()

    def __del__(self):
        self.cmid.close()