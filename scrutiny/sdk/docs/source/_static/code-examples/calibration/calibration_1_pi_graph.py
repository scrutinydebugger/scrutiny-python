from scrutiny.sdk.client import ScrutinyClient
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.sdk import datalogging
import scrutiny.sdk.exceptions
import argparse
import time


class PIController:
    kp: WatchableHandle
    ki: WatchableHandle
    max: WatchableHandle
    min: WatchableHandle
    sat_margin: WatchableHandle
    ref: WatchableHandle
    feedback: WatchableHandle
    output: WatchableHandle

    def __init__(self, client: ScrutinyClient, basepath: str):
        basepath = basepath.rstrip('/')
        self.kp = client.watch(f'{basepath}/m_kp')
        self.ki = client.watch(f'{basepath}/m_ki')
        self.max = client.watch(f'{basepath}/m_max')
        self.min = client.watch(f'{basepath}/m_min')
        self.sat_margin = client.watch(f'{basepath}/m_sat_margin')
        self.ref = client.watch(f'{basepath}/m_ref')
        self.feedback = client.watch(f'{basepath}/m_feedback')
        self.output = client.watch(f'{basepath}/m_out')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--kp', type=float, required=True, help="The proportional gain")
    parser.add_argument('--ki', type=float, required=True, help="The integral gain")
    args = parser.parse_args()

    hostname = 'localhost'
    port = 1234
    client = ScrutinyClient()
    with client.connect(hostname, port, wait_status=True):    # Establish a connection and wait for a first server status update
        client.wait_device_ready(timeout=5)

        controller = PIController(client, '/var/global/m_controller')
        manual_control = client.watch("/var/static/main.cpp/control_task/manual_control")
        set_point = client.watch("/var/static/main.cpp/control_task/manual_control_setpoint")

        client.wait_new_value_for_all()

        controller.kp.value = args.kp
        controller.ki.value = args.ki

        config = datalogging.DataloggingConfig(sampling_rate=0, decimation=1, timeout=0, name="MyGraph")
        config.configure_trigger(datalogging.TriggerCondition.GreaterThan, [set_point, 0], position=0.1, hold_time=0)
        config.configure_xaxis(datalogging.XAxisType.IdealTime)
        pv_axis = config.add_axis('Process Var')
        cmd_axis = config.add_axis('Command')
        config.add_signal(controller.ref, pv_axis, name="Reference")
        config.add_signal(controller.feedback, pv_axis, name="Feedback")
        config.add_signal(controller.output, cmd_axis, name="Command")

        done = False
        actual_set_point = 0.1
        manual_control.value = True
        try:
            while not done:
                set_point.value = 0
                time.sleep(1)   # Wait for stabilization. Setpoint changed to 0
                print(f"Starting the datalogger for setpoint={actual_set_point}")
                request = client.start_datalog(config)
                set_point.value = actual_set_point
                try:
                    # Build a filename based on the actual parameters
                    filename = f"controller_test_kp={args.kp:0.4f}_ki={args.ki:0.4f}_sp_{actual_set_point:0.3f}.csv"
                    acquisition = request.wait_and_fetch(timeout=5)
                    print(f"Acquisition complete. Saving to {filename}")
                    acquisition.to_csv(filename)
                    actual_set_point += 0.1
                    if actual_set_point > 1:
                        done = True
                except scrutiny.sdk.exceptions.TimeoutException as e:
                    done = True
                    print(f"The datalogger failed to catch the event. {e}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            print("Done")
            try:
                manual_control.value = False
            except: pass


if __name__ == '__main__':
    main()
