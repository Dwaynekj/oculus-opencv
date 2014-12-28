"""
Oculus Video: streams two camera feeds into the Oculus Rift after
  having distorted them to account for pincushion effect

Will display on whichever monitor is current when run.

Requires OpenCV 2.4.9, numpy 1.8.1 and ovrsdk

Based directly off of: http://www.argondesign.com/news/2014/aug/26/augmented-reality-oculus-rift/
"""


import sys
import cv2
import numpy as np
import ovrsdk as ovr
import argparse
import time
from math import floor

parser = argparse.ArgumentParser()

parser.add_argument(
    '-l',
    '--left',
    help='Left video device integer value (e.g. /dev/video1 is "1")',
    type=int,
    default=0,
)

parser.add_argument(
    '-r',
    '--right',
    help='Right video device integer value (e.g. /dev/video1 is "1")',
    type=int,
    default=1,
)

parser.add_argument(
    '-w',
    '--write',
    help='Whether to record video to file, off by default to save overhead',
    action='store_true',
)

parser.add_argument(
    '-O',
    '--oculus',
    help='Whether to enable Oculus setup',
    action='store_false',
)

parser.add_argument(
    '-f',
    '--fps',
    help='Frames per second (for recording)',
    default=15,
    type=float,
)

args = parser.parse_args()

def crop(image, _xl, _xr, _yl, _yr, width, height):
    return image[_xl:width-_xr, _yl:height-_yr]

def create_distortion_matrix(_fx, _cx, _fy, _cy):
    matrix = np.array([
        [_fx, 0, _cx],
        [0, _fy, _cy],
        [0, 0, 1]
    ])
    return matrix

def transform(image, matrix):
    image_distortion = cv2.undistort(
        image,
        matrix,
        np.array([0.22, 0.24, 0, 0, 0])
    )
    return image_distortion

def join_images(image_left, image_right):
    return np.append(image_left, image_right, axis=1)

def translate(image, x, y):
    """Oculus DK2 is two images together equal to 2364 x 1461

    Also see the bottom of this page:
    http://www.3dtv.at/knowhow/EncodingDivx_en.aspx
    """
    rows, cols = 480, 720 #288, 384
    matrix = np.float32([[1, 0, x], [0, 1, y]])
    image_translate = cv2.warpAffine(image, matrix, (cols, rows))
    return image_translate

def print_params():
    p = Parameters
    strings = []
    for item in [par for par in dir(p) if par.isalnum()]:
        strings.append("{name} = {value}".format(
            name=item,
            value=getattr(p, item),
        ))
    string = ', '.join(strings)
    print(string)

class Parameters():
    #Matrix coefficients for left eye barrel effect
    fxL = 350
    fyL = 300
    cxL = 310
    cyL = 260

    #Matrix coefficients for right eye barrel effect
    fxR = fxL #257
    fyR = fyL #211
    cxR = cxL #207
    cyR = cyL #138

    #offset to align images
    xL = 0
    yL = 0
    xR = -xL
    yR = -yL

    #offsets to translate image before distortion
    xo = -80
    yo = 20

    #offsets to translate image after distortion
    xo2 = -110
    yo2 = 0

    cropXL = 30
    cropXR = 170
    cropYL = 0
    cropYR = 80

    # width, height, t = left_frame.shape
    width = 720
    height = 480

    # frames per second
    fps = args.fps

def run():
    p = Parameters

    key_mappings = dict(
        fxL=('f', 's'),
        fxR=('f', 's'),
        fyL=('e', 'd'),
        fyR=('e', 'd'),
        cxL=('l', 'j'),
        cxR=('l', 'j'),
        cyL=('k', 'i'),
        cyR=('k', 'i'),
        yo2=('o', 'u'),
        xo2=('m', 'n'),
        xo=('.', ','),
        yo=('h', ';'),
        cropXL=('z', 'x'),
        cropYL=('w', 'r'),
        cropXR=('c', 'v'),
        cropYR=('a', 'g'),
    )

    cR = cv2.VideoCapture(args.right)
    cL = cv2.VideoCapture(args.left)

    if not (cR.isOpened() and cL.isOpened()):
        print('Failed to find two cameras. Are they connected?')
        sys.exit()

    """initializes ovrsdk and starts tracking oculus"""
    ovr.ovr_Initialize()
    hmd = ovr.ovrHmd_Create(0)

    try:
        hmd.contents
    except ValueError as _:
        print('Failed to initialize Oculus, is it connected?')
        if args.oculus:
            sys.exit()

    if args.oculus:
        hmdDesc = ovr.ovrHmdDesc()
        ovr.ovrHmd_GetDesc(hmd, ovr.byref(hmdDesc))
        ovr.ovrHmd_StartSensor(
            hmd,
            ovr.ovrSensorCap_Orientation | ovr.ovrSensorCap_YawCorrection,
            0
        )

        # The device dimensions; should we use them for width/height?
        _ = ovr.ovrHmd_GetFovTextureSize(
            hmd,
            ovr.ovrEye_Left,
            hmdDesc.MaxEyeFov[0],
            1.0
        )
        _ = ovr.ovrHmd_GetFovTextureSize(
            hmd,
            ovr.ovrEye_Right,
            hmdDesc.MaxEyeFov[1],
            1.0
        )

    cv2.namedWindow('vid', 16 | cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(
        "vid",
        cv2.WND_PROP_FULLSCREEN,
        cv2.cv.CV_WINDOW_FULLSCREEN
    )

    video_out = False
    if args.write:
        fourcc = cv2.cv.CV_FOURCC(*'XVID')
        video_out = cv2.VideoWriter(
            'output.avi',
            fourcc,
            p.fps,
            (960, 520), # TODO: make this dynamic
            True # color, not grayscale
        )

    while True:

        _, left_frame = cL.read()
        _, right_frame = cR.read()

        matrixL = create_distortion_matrix(p.fxL, p.cxL, p.fyL, p.cyL)
        matrixR = create_distortion_matrix(p.fxR, p.cxR, p.fyR, p.cyR)

        #translates, crops and distorts image
        left_frame = translate(left_frame, p.xL + p.xo, p.yL + p.yo)
        right_frame = translate(right_frame, p.xR + p.xo, p.yR + p.yo)

        left_frame = transform(left_frame, matrixL)
        right_frame = transform(right_frame, matrixR)

        left_frame = translate(left_frame, p.xo2, p.yo2)
        right_frame = translate(right_frame, p.xo2, p.yo2)

        left_frame = crop(
            left_frame,
            p.cropXL,
            p.cropXR,
            p.cropYL,
            p.cropYR,
            p.width,
            p.height,
        )
        right_frame = crop(
            right_frame,
            p.cropXL,
            p.cropXR,
            p.cropYL,
            p.cropYR,
            p.width,
            p.height,
        )
        composite_frame = join_images(left_frame, right_frame)

        cv2.imshow('vid', composite_frame)

        if video_out:
            video_out.write(composite_frame)

        key = cv2.waitKey(1) & 255
        if key == ord('q'):
            cv2.destroyAllWindows()
            cR.release()
            cL.release()
            print_params()
            if video_out:
                video_out.release()
            break

        elif key == ord('p'):
            print_params()

        for metric, tup in key_mappings.iteritems():
            _add = tup[0]
            _sub = tup[1]
            if key == ord(_add):
                setattr(p, metric, getattr(p, metric) + 10)
            if key == ord(_sub):
                setattr(p, metric, getattr(p, metric) - 10)

        # Don't let these go negative
        for metric in ['cropXL', 'cropYL', 'cropXR', 'cropYR']:
            p_m = getattr(p, metric)
            if p_m < 0:
                print("Attempting to set {} below zero".format(
                    metric
                ))
                setattr(p, metric, 0)

if __name__ == '__main__':
    run()
