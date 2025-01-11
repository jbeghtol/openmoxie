from django.db import connections, transaction
import time

def now_ms():
    return time.time_ns() // 1_000_000

# Execute a block of db interactions inside an atomic transaction
def run_db_atomic(functor, *args, **kwargs):
    with connections['default'].cursor() as cursor:
        with transaction.atomic():
            return functor(*args, **kwargs)