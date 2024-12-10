
class ZMQHandler:
    def __init__(self, server):
        self._server = server
        pass

    def handle_zmq(self, device_id, protoname, protodata):
        print(f'ZMQ Handler RX: {protoname}')

    def zmq_reply(self, device_id, proto):
        self._server.send_zmq_to_bot(device_id, proto)
