#cython: language_level=3, boundscheck=False
import multiprocessing as mp
from enum import Enum
import numpy as np
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
Gst.init(None)

'''Konwn issues

* if format changes at run time system hangs
'''

class StreamMode(Enum):
    INIT_STREAM = 1
    SETUP_STREAM = 1
    READ_STREAM = 2


class StreamCommands(Enum):
    FRAME = 1
    ERROR = 2
    HEARTBEAT = 3
    RESOLUTION = 4
    STOP = 5


class StreamCapture(mp.Process):

    def __init__(self, link, stop, outQueue, framerate):
        """
        Initialize the stream capturing process
        link - rstp link of stream
        stop - to send commands to this process
        outPipe - this process can send commands outside
        """

        super().__init__()
        self.streamLink = link
        self.stop = stop
        self.outQueue = outQueue
        self.framerate = framerate
        self.currentState = StreamMode.INIT_STREAM
        self.pipeline = None
        self.source = None
        self.decode = None
        self.convert = None
        self.sink = None
        self.image_arr = None
        self.newImage = False
        self.frame1 = None
        self.frame2 = None
        self.num_unexpected_tot = 40
        self.unexpected_cnt = 0



    def gst_to_opencv(self, sample):
        buf = sample.get_buffer()
        caps = sample.get_caps()

        # Print Height, Width and Format
        # print(caps.get_structure(0).get_value('format'))
        # print(caps.get_structure(0).get_value('height'))
        # print(caps.get_structure(0).get_value('width'))

        arr = np.ndarray(
            (caps.get_structure(0).get_value('height'),
             caps.get_structure(0).get_value('width'),
             3),
            buffer=buf.extract_dup(0, buf.get_size()),
            dtype=np.uint8)
        return arr

    def new_buffer(self, sink, _):
        sample = sink.emit("pull-sample")
        arr = self.gst_to_opencv(sample)
        self.image_arr = arr
        self.newImage = True
        return Gst.FlowReturn.OK

    def run(self):
        # Create the empty pipeline
        self.pipeline = Gst.parse_launch(
            'rtspsrc name=m_rtspsrc ! rtph264depay name=m_rtph264depay ! avdec_h264 name=m_avdech264 ! videoconvert name=m_videoconvert ! videorate name=m_videorate ! appsink name=m_appsink')

        # source params
        self.source = self.pipeline.get_by_name('m_rtspsrc')
        self.source.set_property('latency', 0)
        self.source.set_property('location', self.streamLink)
        self.source.set_property('protocols', 'tcp')
        self.source.set_property('retry', 50)
        self.source.set_property('timeout', 50)
        self.source.set_property('tcp-timeout', 5000000)
        self.source.set_property('drop-on-latency', 'true')

        # decode params
        self.decode = self.pipeline.get_by_name('m_avdech264')
        self.decode.set_property('max-threads', 2)
        self.decode.set_property('output-corrupt', 'false')

        # convert params
        self.convert = self.pipeline.get_by_name('m_videoconvert')

        #framerate parameters
        self.framerate_ctr = self.pipeline.get_by_name('m_videorate')
        self.framerate_ctr.set_property('max-rate', self.framerate/1)
        self.framerate_ctr.set_property('drop-only', 'true')

        # sink params
        self.sink = self.pipeline.get_by_name('m_appsink')

        # Maximum number of nanoseconds that a buffer can be late before it is dropped (-1 unlimited)
        # flags: readable, writable
        # Integer64. Range: -1 - 9223372036854775807 Default: -1
        self.sink.set_property('max-lateness', 500000000)

        # The maximum number of buffers to queue internally (0 = unlimited)
        # flags: readable, writable
        # Unsigned Integer. Range: 0 - 4294967295 Default: 0
        self.sink.set_property('max-buffers', 5)

        # Drop old buffers when the buffer queue is filled
        # flags: readable, writable
        # Boolean. Default: false
        self.sink.set_property('drop', 'true')

        # Emit new-preroll and new-sample signals
        # flags: readable, writable
        # Boolean. Default: false
        self.sink.set_property('emit-signals', True)

        # # sink.set_property('drop', True)
        # # sink.set_property('sync', False)

        # The allowed caps for the sink pad
        # flags: readable, writable
        # Caps (NULL)
        caps = Gst.caps_from_string(
            'video/x-raw, format=(string){BGR, GRAY8}; video/x-bayer,format=(string){rggb,bggr,grbg,gbrg}')
        self.sink.set_property('caps', caps)

        if not self.source or not self.sink or not self.pipeline or not self.decode or not self.convert:
            print("Not all elements could be created.")
            self.stop.set()

        self.sink.connect("new-sample", self.new_buffer, self.sink)

        # Start playing
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Unable to set the pipeline to the playing state.")
            self.stop.set()

        # Wait until error or EOS
        bus = self.pipeline.get_bus()

        while True:

            if self.stop.is_set():
                print('Stopping CAM Stream by main process')
                break

            message = bus.timed_pop_filtered(10000, Gst.MessageType.ANY)
            # print "image_arr: ", image_arr
            if self.image_arr is not None and self.newImage is True:

                if not self.outQueue.full():

                    # print("\r adding to queue of size{}".format(self.outQueue.qsize()), end='\r')
                    self.outQueue.put((StreamCommands.FRAME, self.image_arr), block=False)

                self.image_arr = None
                self.unexpected_cnt = 0


            if message:
                if message.type == Gst.MessageType.ERROR:
                    err, debug = message.parse_error()
                    print("Error received from element %s: %s" % (
                        message.src.get_name(), err))
                    print("Debugging information: %s" % debug)
                    break
                elif message.type == Gst.MessageType.EOS:
                    print("End-Of-Stream reached.")
                    break
                elif message.type == Gst.MessageType.STATE_CHANGED:
                    if isinstance(message.src, Gst.Pipeline):
                        old_state, new_state, pending_state = message.parse_state_changed()
                        print("Pipeline state changed from %s to %s." %
                              (old_state.value_nick, new_state.value_nick))
                else:
                    print("Unexpected message received.")
                    self.unexpected_cnt = self.unexpected_cnt + 1
                    if self.unexpected_cnt == self.num_unexpected_tot:
                        break


        print('terminating cam pipe')
        self.stop.set()
        self.pipeline.set_state(Gst.State.NULL)