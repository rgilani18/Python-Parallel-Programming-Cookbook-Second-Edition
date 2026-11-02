"""Restaurant simulator demonstrating Python thread synchronization primitives."""

from __future__ import annotations

import argparse
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from queue import Queue
from typing import Callable


@dataclass
class Order:
    number: int
    customer: str
    served: threading.Event


class Statistics:
    """Shared state protected by Lock and RLock."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.rlock = threading.RLock()
        self.created = 0
        self.cooked = 0
        self.served = 0

    def order_created(self) -> None:
        with self.lock:
            self.created += 1

    def _increment(self, attribute: str) -> None:
        setattr(self, attribute, getattr(self, attribute) + 1)

    def cooked_order(self) -> None:
        with self.rlock:
            self._increment("cooked")

    def served_order(self) -> None:
        with self.rlock:
            self._increment("served")

    def snapshot(self) -> tuple[int, int, int]:
        with self.lock:
            return self.created, self.cooked, self.served


class Customer(threading.Thread):
    def __init__(
        self,
        number: int,
        orders: Queue[Order | None],
        tables: threading.Semaphore,
        stats: Statistics,
        log: Callable[[str], None],
    ) -> None:
        super().__init__(name=f"Customer-{number}")
        self.number = number
        self.orders = orders
        self.tables = tables
        self.stats = stats
        self.log = log

    def run(self) -> None:
        order = Order(self.number, self.name, threading.Event())
        self.tables.acquire()
        try:
            self.log(f"{self.name} got table")
            self.stats.order_created()
            self.orders.put(order)
            order.served.wait()
            self.log(f"{self.name} received order #{order.number}")
        finally:
            self.tables.release()


class Chef(threading.Thread):
    def __init__(
        self,
        number: int,
        orders: Queue[Order | None],
        counter: deque[Order],
        counter_condition: threading.Condition,
        counter_capacity: int,
        stats: Statistics,
        log: Callable[[str], None],
        ready: threading.Barrier,
    ) -> None:
        super().__init__(name=f"Chef-{number}")
        self.orders = orders
        self.counter = counter
        self.counter_condition = counter_condition
        self.counter_capacity = counter_capacity
        self.stats = stats
        self.log = log
        self.ready = ready

    def run(self) -> None:
        self.ready.wait()
        while True:
            order = self.orders.get()
            try:
                if order is None:
                    return
                self.log(
                    f"{self.name} (pid={os.getpid()}) cooking order #{order.number}"
                )
                time.sleep(0.03 + (order.number % 3) * 0.01)
                self.stats.cooked_order()
                with self.counter_condition:
                    while len(self.counter) >= self.counter_capacity:
                        self.counter_condition.wait()
                    self.counter.append(order)
                    self.counter_condition.notify_all()
            finally:
                self.orders.task_done()


class Waiter(threading.Thread):
    def __init__(
        self,
        number: int,
        counter: deque[Order],
        counter_condition: threading.Condition,
        closing: threading.Event,
        stats: Statistics,
        log: Callable[[str], None],
        ready: threading.Barrier,
    ) -> None:
        super().__init__(name=f"Waiter-{number}")
        self.counter = counter
        self.counter_condition = counter_condition
        self.closing = closing
        self.stats = stats
        self.log = log
        self.ready = ready

    def run(self) -> None:
        self.ready.wait()
        while True:
            with self.counter_condition:
                while not self.counter and not self.closing.is_set():
                    self.counter_condition.wait()
                if not self.counter and self.closing.is_set():
                    return
                order = self.counter.popleft()
                self.counter_condition.notify_all()
            time.sleep(0.015)
            self.stats.served_order()
            self.log(f"{self.name} served order #{order.number}")
            order.served.set()


def run_simulation(chef_count: int, customer_count: int, verbose: bool = True) -> float:
    started = time.perf_counter()
    orders: Queue[Order | None] = Queue()
    tables = threading.Semaphore(3)
    counter: deque[Order] = deque()
    counter_condition = threading.Condition()
    closing = threading.Event()
    restaurant_open = threading.Event()
    stats = Statistics()
    output_lock = threading.Lock()

    def log(message: str) -> None:
        if verbose:
            with output_lock:
                print(message)

    staff_ready = threading.Barrier(chef_count + 2, action=restaurant_open.set)
    chefs = [
        Chef(i, orders, counter, counter_condition, 5, stats, log, staff_ready)
        for i in range(1, chef_count + 1)
    ]
    waiters = [
        Waiter(i, counter, counter_condition, closing, stats, log, staff_ready)
        for i in range(1, 3)
    ]

    # Barrier: the restaurant opens only after every chef and waiter is ready.
    for worker in chefs + waiters:
        worker.start()
    restaurant_open.wait()
    customers = [
        Customer(i, orders, tables, stats, log)
        for i in range(1, customer_count + 1)
    ]
    for customer in customers:
        customer.start()
        time.sleep(0.005)
    for customer in customers:
        customer.join()

    for _ in chefs:
        orders.put(None)
    for chef in chefs:
        chef.join()

    closing.set()
    with counter_condition:
        counter_condition.notify_all()
    for waiter in waiters:
        waiter.join()

    elapsed = time.perf_counter() - started
    created, cooked, served = stats.snapshot()
    if (created, cooked, served) != (customer_count, customer_count, customer_count):
        raise RuntimeError(
            f"simulation lost an order: created={created}, cooked={cooked}, served={served}"
        )
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Chapter 2 restaurant thread simulator")
    parser.add_argument("--customers", type=int, default=10)
    args = parser.parse_args()
    if args.customers < 1:
        parser.error("--customers must be at least 1")

    print("Restaurant opening with 3 chefs, 2 waiters, and 3 tables")
    three_chef_time = run_simulation(3, args.customers)
    one_chef_time = run_simulation(1, args.customers, verbose=False)
    print(f"\n1 chef:  {one_chef_time:.3f} seconds")
    print(f"3 chefs: {three_chef_time:.3f} seconds")


if __name__ == "__main__":
    main()
