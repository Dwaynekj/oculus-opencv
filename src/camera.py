'''
Camera Reader and Processor classes, based on Gevent's Greenlets
'''


import gevent
from gevent import Greenlet

from algos import *

class CameraReader(Greenlet):
    """Read frames from a camera and apply distortions"""
    def __init__(self, camera, queue):
        """Save the camera (to read from) and queue (to write to)"""
        Greenlet.__init__(self)
        self.camera = camera
        self.queue = queue

    def _run(self):
        """Iterate and process frames indefinitely

        Assumes the application will be shutdown through other means
        (namely, the CameraProcessor greenlet, which handles user
        input).

        Reads a frame in from the camera, applies translations and
        distortions based on the Parameters class, then writes the
        final image to the output queue.
        """
        par = Parameters
        while True:
            _, frame = self.camera.read()

            matrix = create_distortion_matrix(
                par.fxL, par.cxL, par.fyL, par.cyL
            )
            frame = translate(frame, par.xL + par.xo, par.yL + par.yo)
            frame = transform(frame, matrix)
            frame = translate(frame, par.xo2, par.yo2)

            frame = crop(
                frame,
                par.cropXL,
                par.cropXR,
                par.cropYL,
                par.cropYR,
            )
            self.queue.put(frame)
            gevent.sleep(0)

    def __str__(self):
        return 'CameraReader for {}'.format(self.camera)

class CameraProcessor(Greenlet):
    """Parse video frames from two queues and stitch them together.

    Uses algos.join_images to stitch the left and right video frames
    into one wider image and displays that image via `cv2.imshow`.

    If args.write is set, creates an OpenCV VideoWriter and saves
    the composited frames on each iteration. NOTE/TODO: frame rate
    from the USB cameras is pretty low (~15 fps). If you set args.fps
    too high, the output video will run too fast (sped-up).
    """
    def __init__(self, left_queue, right_queue, write=False):
        """Stores queues and whether to write video to file.

        Args:
            left_queue (gevent.queue): queue for left image frames
            right_queue (gevent.queue): queue for right image frames
            write (boolean): Whether to write video to file
        """
        Greenlet.__init__(self)
        self.left = left_queue
        self.right = right_queue

        self.video_out = False
        if write:
            fourcc = cv2.cv.CV_FOURCC(*'XVID')
            self.video_out = cv2.VideoWriter(
                'output.avi', # TODO: Use a program argument
                fourcc,
                Parameters.fps,
                (800, 450), # TODO: make this dynamic
                True # color, not grayscale
            )

    def _run(self):
        while True:
            self.iterate()
            gevent.sleep(0)

    def iterate(self):
        """Consumes frames from the queues and display

        If the two queues contain frames, read them in and create
        the composited image, then display to the user. Also handles
        user input.
        """
        if not (self.left.empty() and self.right.empty()):
            composite_frame = join_images(
                self.left.get(),
                self.right.get(),
            )
            cv2.imshow('vid', composite_frame)

            if self.video_out:
                self.video_out.write(composite_frame)

class InputHandler(Greenlet):
    """Handle user input

    Handles keyboard input, allowing for `q`uiting the program
    and changing parameters during run-time. Not really related to
    cameras, but subclasses Greenlet, like the CameraReader/Processor.
    """
    def __init__(self, callback):
        """Stores shutdown callback.

        Args:
            callback (function): the method to run on application
               shutdown (holds references to objects that this class
               doesn't necessarily know about (e.g. the cv2 cameras)
        """
        Greenlet.__init__(self)
        self.callback = callback

    def _run(self):
        """Greenlet method; here we loop indefinitely"""
        while True:
            self.handle_input()
            gevent.sleep(0)

    def handle_input(self):
        """Read user input and react

        Allow for `q`uiting the application and changing run-time
        parameters. We use the `Parameters.key_mappings` and iterate
        over them to increment or decrement the associated parameter
        (see also the documentation in the Parameters class).
        """
        key = cv2.waitKey(1) & 255
        if key == ord('q'):
            self.callback()
            self.kill()

        elif key == ord('p'):
            print_params()

        for metric, tup in Parameters.key_mappings.iteritems():
            _add = tup[0]
            _sub = tup[1]
            if key == ord(_add):
                setattr(
                    Parameters,
                    metric,
                    getattr(Parameters, metric) + 10
                )
            if key == ord(_sub):
                setattr(
                    Parameters,
                    metric,
                    getattr(Parameters, metric) - 10
                )

        # Don't let these go negative
        for metric in ['cropXL', 'cropYL', 'cropXR', 'cropYR']:
            p_m = getattr(Parameters, metric)
            if p_m < 0:
                print("Attempting to set {} below zero".format(
                    metric
                ))
                setattr(Parameters, metric, 0)

    def __str__(self):
        return 'InputHandler'