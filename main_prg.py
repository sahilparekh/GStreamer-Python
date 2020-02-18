#!/usr/bin/env python3
'''\
This Simple program Demonstrates how to use G-Streamer and capture RTSP Frames
in Opencv using Python
     - Sahil Parekh
'''

import multiprocessing as mp
import time
import vid_streamv3 as vs
import cv2


class mainStream:
    def __init__(self, camlink):
        # Current Cam
        self.camProcess = None
        self.cam_queue = None
        self.stopbit = None
        self.camlink = camlink
        self.framerate = 6

    def start(self):
        # set queue size
        self.cam_queue = mp.Queue(maxsize=100)

        # get all cams
        time.sleep(3)

        self.stopbit = mp.Event()
        self.camProcess = vs.StreamCapture(
            self.camlink,
            self.stopbit,
            self.cam_queue,
            self.framerate
        )
        self.camProcess.start()

        try:
            while True:

                if not self.cam_queue.empty():
                    # print('Got frame')
                    cmd, val = self.cam_queue.get()

                    '''
                    #calculate FPS
                    diffTime = time.time() - lastFTime`
                    fps = 1 / diffTime
                    # print(fps)
                    '''
                    # if cmd == vs.StreamCommands.RESOLUTION:
                    #     pass #print(val)

                    if cmd == vs.StreamCommands.FRAME:
                        if val is not None:
                            cv2.imshow('Cam: ' + self.camlink, val)
                            cv2.waitKey(1)

        except KeyboardInterrupt:
            print('Caught Keyboard interrupt')

        except Exception as e:
            print('Caught Main Exception')
            print(e)

        self.stopCamStream()
        cv2.destroyAllWindows()

    def stopCamStream(self):
        print('in stopCamStream')

        if self.stopbit is not None:
            self.stopbit.set()
            while not self.cam_queue.empty():
                try:
                    _ = self.cam_queue.get()
                except Exception:
                    break
                self.cam_queue.close()

            self.camProcess.join()


if __name__ == "__main__":
    import os
    stream = mainStream(os.environ["CAMERA_URL"])
    stream.start()
