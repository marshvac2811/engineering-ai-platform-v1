import threading
from jobs.threadlocal_client import ThreadLocalClient


def test_each_thread_gets_its_own_client_and_reuses_it():
    made = []
    def factory():
        o = object(); made.append(o); return type("C", (), {"ident": id(o), "table": lambda self, n: n})()
    c = ThreadLocalClient(factory)
    assert c.table("x") == "x" and c.ident == c.ident and len(made) == 1
    seen = []
    t = threading.Thread(target=lambda: seen.append(c.ident)); t.start(); t.join()
    assert len(made) == 2 and seen[0] != c.ident
