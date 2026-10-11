import threading
def sync():
    print("Thread started...")
    threading.Event().wait(1)
    print("Thread finished!")
