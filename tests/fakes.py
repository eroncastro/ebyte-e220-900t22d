class FakeUART:
    """Stand-in for machine.UART.

    Mirrors real serial behavior: read() returns None until a response has
    been armed by a preceding write(). Responses are consumed from `queue`
    in order, one per write(). Set `pending` directly in a test to simulate
    stale/garbage bytes sitting in the buffer before any write happens.

    `incoming` is separate: it feeds read() directly without needing a
    write() first, for testing unsolicited receive() traffic.
    """

    def __init__(self, queue=None, incoming=None):
        self.queue = list(queue or [])
        self.incoming = list(incoming or [])
        self.pending = None
        self.written = []

    def write(self, data):
        self.written.append(bytes(data))
        if self.queue:
            self.pending = self.queue.pop(0)

    def read(self, size=None):
        # `size` is accepted to match machine.UART.read([nbytes]); the fake
        # hands back whole queued chunks and does not honor it.
        if self.pending is not None:
            value, self.pending = self.pending, None
            return value
        if self.incoming:
            return self.incoming.pop(0)
        return None


class FakePin:
    """Stand-in for machine.Pin, tracking every value() write."""

    def __init__(self, initial=None):
        self._value = initial
        self.history = []

    def value(self, val=None):
        if val is None:
            return self._value
        self._value = val
        self.history.append(val)


class FakeAux:
    """Stand-in for the module's AUX pin (input-only, read via value()).

    Reports low (busy) for the first `busy_reads` calls, then high (idle).
    Set `remaining_busy` directly to re-arm it after construction.
    """

    def __init__(self, busy_reads=0):
        self.remaining_busy = busy_reads
        self.reads = 0

    def value(self):
        self.reads += 1
        if self.remaining_busy > 0:
            self.remaining_busy -= 1
            return 0
        return 1
