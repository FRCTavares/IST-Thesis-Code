import json
import zmq
import time

class ZmqPublisher:
    def __init__(self, bind="tcp://0.0.0.0:5555", topic=b"dets"):
        self.topic = topic
        self.topic_prefix = topic + b" "   # IMPORTANT: trailing space
        ctx = zmq.Context.instance()
        self.s = ctx.socket(zmq.PUB)
        self.s.setsockopt(zmq.SNDHWM, 5)
        self.s.bind(bind)
        time.sleep(0.2)

    def send(self, dets, frame_id=None, extra=None):
        msg = {"dets": dets}
        if frame_id is not None:
            msg["frame_id"] = frame_id
        if extra:
            msg.update(extra)

        payload = json.dumps(msg, separators=(",", ":")).encode("utf-8")

        # Single-frame wire format: b"dets " + b"{...json...}"
        self.s.send(self.topic_prefix + payload)