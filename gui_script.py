#!/usr/bin/env python
import subprocess as sp
import tkinter as tki
import shlex
import logging

from hotqueue import DeHotQueue

logger = logging.getLogger(__name__)

QNAME = 'tk_queue'
WORKER_PATH = 'worker_script.py'

MAX = 5


class ProcessManager:
    def __init__(self, process_args, qname):
        self.process_args = process_args
        self.queue = DeHotQueue(qname)
        self.processes = []
        self.logger = logging.getLogger(f'{__name__}.{type(self).__name__}')
        logger.info(f"Worker created with args {' '.join(process_args)} and queue {qname}")

    def prune(self):
        unfinished = []
        finished = dict()
        for process in self.processes:
            response = process.poll()
            if response is None:
                unfinished.append(process)
            else:
                finished[process.pid] = process.returncode

        self.processes = unfinished
        return finished

    def _start_process(self, n=1):
        for _ in range(n):
            self.processes.append(sp.Popen(self.process_args + [self.queue.name]))

    def _stop_process(self, n=1):
        if n is None:
            n = self.process_count

        for _ in range(n):
            self.queue.put_front(None)

    @property
    def process_count(self):
        return len(self.processes)

    @process_count.setter
    def process_count(self, value):
        if not isinstance(value, int):
            raise TypeError(f"Value must be an integer, got {type(value)}")

        self.prune()
        diff = value - self.process_count
        if diff < 0:
            self._stop_process(abs(diff))
        elif diff > 0:
            self._start_process(diff)

    def enqueue(self, *items):
        for item in items:
            self.logger.debug(f"enqueuing {item}")
        self.queue.put(*items)

    def clear_queue(self):
        self.queue.clear()

    def killall(self):
        for process in self.processes:
            process.kill()
        self.join()

    def join(self):
        for process in self.processes:
            process.wait()
        self.processes = []

    def __enter__(self):
        return self

    def close(self):
        self.process_count = 0
        self.join()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.close()
        else:
            self.killall()


def cli_main():
    with ProcessManager(['python', WORKER_PATH], QNAME) as manager:
        manager.enqueue(*range(100))
        while True:
            try:
                value = int(input("Enter desired process count: "))
            except (ValueError, TypeError):
                continue
            manager.process_count = value


class Widget(tki.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.logger = logging.getLogger(f'{__name__}.{type(self).__name__}')
        self.manager = None

        self.master = master

        self.master.title('Process Manager')

        row = 0

        # worker script controls
        self.current_worker = ''

        self.queue_label = tki.Label(master, text="Script:")
        self.queue_label.grid(row=row, column=0, sticky=tki.W)

        self.worker_script = tki.StringVar()
        self.worker_script_entry = tki.Entry(master, textvariable=self.worker_script)
        self.worker_script_entry.grid(row=row, column=1, columnspan=2)
        row += 1

        # queue name controls
        self.current_queue = ''
        self.queue_label = tki.Label(master, text="Queue name:")
        self.queue_label.grid(row=row, column=0, sticky=tki.W)

        self.queue_name = tki.StringVar()
        self.queue_name_entry = tki.Entry(master, textvariable=self.queue_name)
        self.queue_name_entry.grid(row=row, column=1, columnspan=2)
        row += 1

        self.worker_set = tki.Button(master, text="Set", command=self.set_worker)
        self.worker_set.grid(row=row, column=0, columnspan=3, sticky=tki.W + tki.E)
        row += 1

        # queue item controls
        self.valid_chars = set('0123456789,:-')
        self.item = tki.StringVar()
        self.item_label = tki.Label(master, text="Item:")
        self.item_label.grid(row=row, column=0)
        self.item_entry = tki.Entry(master, textvariable=self.item)
        self.item_entry.grid(row=row, column=1)
        self.item_button = tki.Button(master, text="Add", command=self.enqueue)
        self.item_button.grid(row=row, column=2)
        row += 1

        # process count controls
        self.count = tki.IntVar()
        self.count.set(0)

        self.subtract_button = tki.Button(master, text="-", command=lambda: self.change(-1))
        self.subtract_button.grid(row=row, column=0, sticky=tki.W)

        self.count_label = tki.Label(master, textvariable=self.count)
        self.count_label.grid(row=row, column=1)

        self.add_button = tki.Button(master, text="+", command=lambda: self.change(1))
        self.add_button.grid(row=row, column=2, sticky=tki.E)
        row += 1

        # reset and kill
        self.clear_button = tki.Button(master, text="Clear", command=self.clear)
        self.clear_button.grid(row=row, column=0, columnspan=3, sticky=tki.W + tki.E)
        row += 1

        self.reset_button = tki.Button(master, text="Reset", command=lambda: self.change(None))
        self.reset_button.grid(row=row, column=0, columnspan=3, sticky=tki.W + tki.E)
        row += 1

        self.kill_button = tki.Button(master, text="Kill", command=self.kill)
        self.kill_button.grid(row=row, column=0, columnspan=3, sticky=tki.W + tki.E)

    def clear(self):
        if not self.manager:
            return

        self.manager.queue.clear()

    def enqueue(self):
        logger.debug("enqueuing")
        if not self.manager:
            return

        s = ''.join(c for c in self.item.get() if c in self.valid_chars)
        for item in s.split(','):
            rng = item.split(':')
            if len(rng) == 1:
                self.manager.enqueue(int(rng[0]))
                continue
            elif len(rng) == 2:
                start_str, stop_str = rng
                step = 1
            elif len(rng) == 3:
                start_str, stop_str, step_str = rng
                step = int(step_str)
            else:
                continue

            start = int(start_str) if start_str else 0
            stop = int(stop_str)
            self.manager.enqueue(*range(start, stop, step))

    def set_worker(self):
        self.logger.debug("setting worker")
        worker = self.worker_script.get().strip()
        qname = self.queue_name.get().strip()
        if worker == self.current_worker and qname == self.current_queue:
            return
        if self.manager:
            self.manager.killall()
        self.manager = ProcessManager(shlex.split(worker), qname)
        self.manager.process_count = self.count.get()
        self.current_worker = worker
        self.current_queue = qname

    def change(self, n=None):
        if n is None:
            new_val = 0
        else:
            new_val = self.count.get() + n
            new_val = min(new_val, MAX)
            new_val = max(new_val, 0)
        self.count.set(new_val)
        self.manager.process_count = new_val

    def kill(self):
        self.manager.killall()


def gui_main():
    root = tki.Tk()
    gui = Widget(root)
    gui.mainloop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.NOTSET)
    # cli_main()
    gui_main()
