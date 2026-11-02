# Restaurant Simulator

This project demonstrates the thread-synchronization concepts from Chapter 2
using a command-line restaurant simulation.

The simulation contains:

- Customers who create and wait for orders
- Chefs who cook orders
- Waiters who serve cooked orders
- Three restaurant tables
- A serving counter with a capacity of five dishes

## Run the program

From the `Chapter02` directory, run:

```powershell
python .\implementation\restaurant_sim.py
```

By default, the program creates 10 customers. To choose another number:

```powershell
python .\implementation\restaurant_sim.py --customers 20
```

The program also compares the processing time of one chef with three chefs.

## Chapter 2 concepts demonstrated

### Thread subclasses

`Customer`, `Chef`, and `Waiter` inherit from `threading.Thread`. Their
parallel work is implemented in their `run()` methods.

### Queue

Customers put `Order` objects into a thread-safe `Queue`. Chefs retrieve those
orders. `task_done()` marks each queue item as processed.

### Semaphore

The restaurant creates:

```python
tables = threading.Semaphore(3)
```

Only three customers can hold tables at one time. A customer calls
`acquire()` before sitting and `release()` after leaving.

### Lock

`Statistics.lock` protects the number of created orders. The output lock also
prevents messages from different threads from being mixed together.

### RLock

`Statistics.rlock` protects cooked and served counters. An `RLock` can be
acquired more than once by the same thread, which makes it suitable for
operations that may call other locked methods.

### Condition

Chefs produce cooked orders into a serving counter, while waiters consume them.
The `Condition` makes chefs wait when the counter is full and makes waiters wait
when it is empty.

The `while` loops around `wait()` re-check the state after waking, which is the
safe condition-variable pattern.

### Event

Every order has an event. A customer waits with `order.served.wait()` until a
waiter calls `order.served.set()`.

The `restaurant_open` event signals that staff preparation is complete. The
`closing` event tells waiters that no additional orders will arrive.

### Barrier

All chefs and waiters wait at a `Barrier`. The restaurant opens only after all
staff members reach that point.

### Thread names and process ID

Threads are named `Customer-1`, `Chef-1`, and so on. Chef output also displays
the process ID using `os.getpid()`. All threads share the same process ID.

### Joining threads

The main thread calls `join()` for customers, chefs, and waiters. This ensures
the program exits only after all work has finished.

## Program flow

1. Create the order queue, table semaphore, serving counter, events, barrier,
   and shared statistics.
2. Start all chefs and waiters.
3. Staff reach the barrier and the restaurant opens.
4. Customers acquire tables and put orders into the queue.
5. Chefs cook orders and place them on the serving counter.
6. Waiters remove cooked orders and signal the corresponding customers.
7. Customers leave and release their tables.
8. Sentinel values stop the chefs after all orders are processed.
9. The closing event stops the waiters.
10. The program verifies that every order was created, cooked, and served.
11. The program compares one-chef and three-chef execution times.

## Example output

```text
Restaurant opening with 3 chefs, 2 waiters, and 3 tables
Customer-1 got table
Chef-1 (pid=12345) cooking order #1
Waiter-2 served order #1
Customer-1 received order #1

1 chef:  0.436 seconds
3 chefs: 0.234 seconds
```

The exact order of messages and timing will vary because threads are scheduled
concurrently.
