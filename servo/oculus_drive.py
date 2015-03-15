import ovrsdk as ovr
from time import sleep
#from servo import move
import pololu as po

def oculus():
    """initializes ovrsdk and starts tracking oculus"""
    ovr.ovr_Initialize()
    hmd = ovr.ovrHmd_Create(0)

    try:
        hmd.contents
    except ValueError as _:
        print('Failed to initialize Oculus, is it connected?')
        if args.oculus:
            sys.exit()

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

    return hmd

from getch import getch
from numpy import interp

if __name__ == '__main__':
    hmd = oculus()
    servo = po.open_serial(COUNT)

    pitch_domain = [-0.3, 0.7]
    yaw_domain = [-0.7, 0.7]
    pitch_range = [0, 180]
    yaw_range = [15, 165]

    map_pitch = lambda x: int(interp(-1 *x, pitch_domain, pitch_range))
    map_yaw = lambda x: int(interp(x, yaw_domain, yaw_range))

    range0 = 90
    range1 = 45

    po.set_target(servo, 1, range0)
    po.set_target(servo, 1, range1)

    while True:
        state = ovr.ovrHmd_GetSensorState(
            hmd, ovr.ovr_GetTimeInSeconds()
        )
	pose = state.Predicted.Pose

        pitch = pose.Orientation.x # -0.3 ~ 0.7
        #roll = pose.Orientation.z
        yaw = pose.Orientation.y # -0.7 ~ 0.7

	#print "%10f" % ( pitch )


        range0 = map_yaw(yaw)
        range1 = map_pitch(pitch)

        print("Servo 0 set to {}, servo 1 set to {}".format(range0, range1))
        po.set_target(servo, 0, range0)
        po.set_target(servo, 1, range1)

        sleep(0.05)
