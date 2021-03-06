
import time
import msgpack

from bw2python.bwtypes import PayloadObject
from bw2python.client import Client
from xbos.util import read_self_timeout

class Plug(object):
    def __init__(self, client=None, uri=None):
        self.client = client
        self._uri = uri.rstrip('/')
        self._state = {
         "cumulative": None,
         "current": None,
         "power": None,
         "state": None,
         "time": None,
         "voltage": None,
        }
        def _handle(msg):
            for po in msg.payload_objects:
                if po.type_dotted == (2,1,1,2):
                    data = msgpack.unpackb(po.content)
                    for k,v in data.items():
                        self._state[k] = v
        # check liveness
        liveness_uri = "{0}/!meta/lastalive".format(uri)
        res = self.client.query(liveness_uri)
        if len(res) == 0:
            raise Exception("No liveness message found at {0}. Is this URI correct?".format(liveness_uri))
        alive = msgpack.unpackb(res[0].payload_objects[0].content)
        ts = alive['ts'] / 1e9
        if time.time() - ts > 30:
            raise Exception("{0} more than 30sec old. Is this URI current?".format(liveness_uri))
        print "Got Plug at {0} last alive {1}".format(uri, alive['val'])

        self.client.subscribe("{0}/signal/info".format(uri), _handle)

    @property
    def cumulative(self, timeout=30):
        return read_self_timeout(self, 'cumulative', timeout)

    @property
    def current(self, timeout=30):
        return read_self_timeout(self, 'current', timeout)

    @property
    def power(self, timeout=30):
        return read_self_timeout(self, 'power', timeout)

    @property
    def state(self, timeout=30):
        return read_self_timeout(self, 'state', timeout)

    @property
    def voltage(self, timeout=30):
        return read_self_timeout(self, 'voltage', timeout)


    def write(self, state):
        po = PayloadObject((2,1,1,2), None, msgpack.packb(state))
        self.client.publish('{0}/slot/state'.format(self._uri),payload_objects=(po,))

    def set_state(self, value):
        self.write({'state': value})

