import argparse
import logging

from pyverbs.enums import IBV_QPT_UD, IBV_QPT_RC, IBV_WR_SEND, IBV_WR_RDMA_WRITE, IBV_WR_RDMA_READ


class DictAction(argparse.Action):
    def __call__(self, parsers, namespace, values, option_string=None):
        setattr(namespace, self.dest, self.choices.get(values))


qp_dict = {'rc': IBV_QPT_RC, 'ud': IBV_QPT_UD}
op_dict = {'send': IBV_WR_SEND, 'write': IBV_WR_RDMA_WRITE, 'read': IBV_WR_RDMA_READ}


class ArgsParser(object):
    def __init__(self):
        self.args = None

    @staticmethod
    def parse_args():
        arg_parser = argparse.ArgumentParser(description="A Python Test Program for RDMA.")
        arg_parser.add_argument('server_ip', type=str, nargs='?',
                                help='The IP address of the Server (Client only).')
        arg_parser.add_argument('-C', '--use_cm', action='store_true',
                                help='Use Connection Management protocol to handshake.')
        arg_parser.add_argument('-d', '--ib_dev', required=True,
                                help='RDMA device to run the tests on.')
        arg_parser.add_argument('-G', '--sg_depth', type=int, default=1,
                                help='Number of sge in the sgl.')
        arg_parser.add_argument('-I', '--inline_size', type=int, default=0,
                                help='Max size of message to be sent in inline.')
        arg_parser.add_argument('-m', '--mtu', type=int, default=4, choices=range(0, 5),
                                help='The Path MTU 0 ~ 4 (256/512/1024/2048/4096).')
        arg_parser.add_argument('-n', '--iters', type=int, default=1,
                                help='Number of exchanges (at least 5, default 1).')
        arg_parser.add_argument('-p', '--port', type=int, default=18515,
                                help='Listen on/connect to port <port> (default 18515).')
        arg_parser.add_argument('-r', '--rx_depth', type=int, default=16,
                                help='Size of rx queue (default 16). If using srq, rx-depth controls max-wr size of the srq.')
        arg_parser.add_argument('-s', '--size', type=int, default=13,
                                help='Size of message to exchange (default 13).')
        arg_parser.add_argument('-S', '--sl', type=int, default=0,
                                help='Service Level (default 0).')
        arg_parser.add_argument('-o', '--operation_type', default=IBV_WR_SEND, choices=op_dict, action=DictAction,
                                help='The type of operation.')
        arg_parser.add_argument('-t', '--tx_depth', type=int, default=16,
                                help='Size of tx queue (default 16).')
        arg_parser.add_argument('-T', '--qp_type', type=str, default=IBV_QPT_RC, choices=qp_dict, action=DictAction,
                                help='The type of QP.')
        arg_parser.add_argument('-v', '--version', action='version', version='%(prog)s version : v0.01',
                                help='Show the version')
        arg_parser.add_argument('-x', '--gid_index', type=int, default=1,
                                help='The index of source gid to communicate with remote peer.')

        # TODO: Check the range and raise an error, for example:
        # https://stackoverflow.com/questions/18700634/python-argparse-integer-condition-12

        return vars(arg_parser.parse_args())


parser = ArgsParser()