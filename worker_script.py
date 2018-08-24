#!/usr/bin/env python
import time
import os
import sys

from hotqueue import HotQueue


def main():
    pid = os.getpid()
    print(f"{pid} starting")
    for item in HotQueue(sys.argv[1]).consume():
        if item is None:
            print(f"{pid} terminating")
            return
        print(f"{item} printed by {pid}")
        time.sleep(2)


if __name__ == '__main__':
    main()
