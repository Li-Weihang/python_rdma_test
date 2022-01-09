#!/usr/bin/python3.8
import sys

sys.path.append('..')

from utils.connection import SKT, CM
from utils.param_parser import parser

from pyverbs.addr import AH, AHAttr, GlobalRoute
from pyverbs.cq import CQ
from pyverbs.device import Context
from pyverbs.enums import *
from pyverbs.mr import MR
from pyverbs.pd import PD
from pyverbs.qp import QP, QPCap, QPInitAttr, QPAttr
from pyverbs.wr import SGE, RecvWR, SendWR


RECV_WR = 1
SEND_WR = 2
GRH_LENGTH = 40

# TODO: Error handling

args = parser.parse_args()

server = not bool(args['server_ip'])

if args['use_cm']:
    conn = CM(args['port'], args['server_ip'])
else:
    conn = SKT(args['port'], args['server_ip'])

print('-' * 80)
print(' ' * 25, "Python test for RDMA")

if server:
    print("Running as server...")
else:
    print("Running as client...")

print('-' * 80)

if args['qp_type'] == IBV_QPT_UD and args['operation_type'] != IBV_WR_SEND:
    print("UD QPs don't support RDMA operations.")
    conn.close()

conn.handshake()

ctx = Context(name=args['ib_dev'])
pd = PD(ctx)
cq = CQ(ctx, 100)

cap = QPCap(max_send_wr=args['tx_depth'], max_recv_wr=args['rx_depth'], max_send_sge=args['sg_depth'],
            max_recv_sge=args['sg_depth'], max_inline_data=args['inline_size'])
qp_init_attr = QPInitAttr(qp_type=args['qp_type'], scq=cq, rcq=cq, cap=cap, sq_sig_all=True)
qp = QP(pd, qp_init_attr)

gid = ctx.query_gid(port_num=1, index=args['gid_index'])

# Handshake to exchange information such as QP Number
remote_info = conn.handshake(gid=gid, qpn=qp.qp_num)

gr = GlobalRoute(dgid=remote_info['gid'], sgid_index=args['gid_index'])
ah_attr = AHAttr(gr=gr, is_global=1, port_num=1)

if args['qp_type'] == IBV_QPT_UD:
    ah = AH(pd, attr=ah_attr)
    qp.to_rts(QPAttr())
else:
    qa = QPAttr()
    qa.ah_attr = ah_attr
    qa.dest_qp_num = remote_info['qpn']
    qa.path_mtu = args['mtu']
    qa.max_rd_atomic = 1
    qa.max_dest_rd_atomic = 1
    qa.qp_access_flags = IBV_ACCESS_REMOTE_WRITE | IBV_ACCESS_REMOTE_READ | IBV_ACCESS_LOCAL_WRITE
    if server:
        qp.to_rtr(qa)
    else:
        qp.to_rts(qa)

conn.handshake()

mr_size = args['size']
if server:
    if args['qp_type'] == IBV_QPT_UD:   # UD needs more space to store GRH when receiving.
        mr_size = mr_size + GRH_LENGTH
    content = 's' * mr_size
else:
    content = 'c' * mr_size

mr = MR(pd, mr_size, IBV_ACCESS_LOCAL_WRITE | IBV_ACCESS_REMOTE_WRITE | IBV_ACCESS_REMOTE_READ)
sgl = [SGE(mr.buf, mr.length, mr.lkey)]

if args['operation_type'] != IBV_WR_SEND:
    remote_info = conn.handshake(addr=mr.buf, rkey=mr.rkey)

def read_mr(mr):
    if args['qp_type'] == IBV_QPT_UD and server:
        return mr.read(mr.length - GRH_LENGTH, GRH_LENGTH).decode()
    else:
        return mr.read(mr.length, 0).decode()    

for i in range(args['iters']):
    print("Iter: " + f"{i + 1}/{args['iters']}")

    mr.write(content, len(content))
    print("MR Content before test:" + read_mr(mr))

    if server and args['operation_type'] == IBV_WR_SEND:
        wr = RecvWR(RECV_WR, len(sgl), sgl)
        qp.post_recv(wr)

    conn.handshake()

    if not server:
        wr = SendWR(SEND_WR, opcode=args['operation_type'], num_sge=1, sg=sgl)
        if args['qp_type'] == IBV_QPT_UD:
            wr.set_wr_ud(ah, remote_info['qpn'], 0)
        elif args['operation_type'] != IBV_WR_SEND:
            wr.set_wr_rdma(remote_info['rkey'], remote_info['addr'])

        qp.post_send(wr)

    conn.handshake()

    if not server or args['operation_type'] == IBV_WR_SEND:
        wc_num, wc_list = cq.poll()

    print("MR Content after test:" + read_mr(mr))

conn.handshake()
conn.close()

print('-' * 80)