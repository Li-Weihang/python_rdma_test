# python_rdma_test

This is an RDMA program written in Python, based on the Pyverbs provided by the rdma-core(https://github.com/linux-rdma/rdma-core) repository.



# How to run

1. Clone the rdma-core repository.

2. Follow README.md of rdma-core and then build the project, please make sure pyverbs is compliled successfully.

3. Set PYTHONPATH to let the Python interpreter find where Pyverbs is.

4. Run rdma_test.py.



# Example

1. Show help
  ```bash
 PYTHONPATH=../rdma-core/build/python/ ./rdma.py -h
  ```

2. Run RDMA Write between two nodes with RC QP:
- Server
```bash
PYTHONPATH=../rdma-core/build/python/ ./rdma.py -d rxe_0 -o write
```

- Client
```bash
PYTHONPATH=../rdma-core/build/python/ ./rdma.py -d rxe_0 -o write 192.168.xx.xx
```
