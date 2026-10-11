# Python Decorators Explained
import time
from functools import wraps

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"{func.__name__} took {end-start:.4f} secs")
        return result
    return wrapper

@timer
def long_running_task():
    time.sleep(1)
    return "Done!"

long_running_task()
