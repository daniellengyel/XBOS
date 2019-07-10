# getting the utils file here
import os, sys
import xbos_services_getter as xsg
import datetime
import calendar
import pytz
import numpy as np
import pandas as pd
import itertools
import time
from pathlib import Path
import pickle
import yaml


def load_model(config):
    building, zone = config["building"], config["zone"]

    model_dir = Path(__file__).parent / "saved_models" / building
    if not os.path.isdir(model_dir):
        os.makedirs(model_dir)

    dir_path = model_dir / (zone + "_" + config["method"] + "_" + str(config["is_second_order"]) + "_" + str(
        config["use_occupancy"]) + "_" + str(config["curr_action_timesteps"]) + "_" + str(
        config["prev_action_timesteps"]))

    if os.path.isdir(str(dir_path)):
        try:
            with open(str(dir_path / "model.pkl"), "rb") as f:
                model = pickle.load(f)
            with open(str(dir_path / "feature_order.pkl"), "rb") as f:
                feature_order = pickle.load(f)
            with open(str(dir_path / "config.pkl"), "rb") as f:
                config = pickle.load(f)
            return model, feature_order, config, None
        except:
            return None, None, None, "Missing model files in dir: " + str(dir_path)

    return None, None, None, "No Model Folder found"


def get_window_in_sec(s):
    """Returns number of seconds in a given duration or zero if it fails.
    Supported durations are seconds (s), minutes (m), hours (h), and days(d)."""
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        return int(float(s[:-1])) * seconds_per_unit[s[-1]]
    except:
        return 0


class ThermalModel:
    _INTERVAL = "5m"  # minutes # TODO allow for getting multiples of 5. Prediction horizon.

    THERMAL_MODELS = {}

    def __init__(self):
        pass

    def check_thermal_model(self, building, zone):
        if building not in ThermalModel.THERMAL_MODELS or zone not in ThermalModel.THERMAL_MODELS[building]:
            # TODO ERROR CHECK.
            config = {
                "start": None,
                "end": None,
                "prediction_window": "5m",
                "raw_data_granularity": "1m",
                "train_ratio": 1,
                "check_data": False,
                "method": "OLS",
                "is_second_order": True,
                "use_occupancy": False,
                "curr_action_timesteps": 0,
                "prev_action_timesteps": -1
            }
            config["building"] = building
            config["zone"] = zone

            thermal_model, column_order, config, err = load_model(config)
            if err is not None:
                return None, err
            if building not in ThermalModel.THERMAL_MODELS:
                ThermalModel.THERMAL_MODELS[building] = {}
            ThermalModel.THERMAL_MODELS[building][zone] = (thermal_model, column_order)

        return None, None

    def prediction(self, building, zone, current_time, action, indoor_temperature, previous_indoor_temperature,
                   outside_temperature, other_zone_temperatures, temperature_unit, print_msg=False):
        """Returns temperature prediction for a given request or None."""
        if print_msg:
            print("received request:", building, zone, current_time,
                  indoor_temperature, outside_temperature, other_zone_temperatures,
                  temperature_unit)

        request_length = [len(building), len(zone), current_time,
                          indoor_temperature, outside_temperature, other_zone_temperatures,
                          len(temperature_unit)]

        unit = "F"  # fahrenheit for now .

        if any(v == 0 for v in request_length):
            return None, None, None, "invalid request, empty params"
        if not (0 <= action <= 2):
            return None, None, None, "Action is not between 0 and 2."

        # TODO Check if valid building/zone/temperature unit/zone, outside and indoor temperature (not none)

        current_time_datetime = datetime.datetime.utcfromtimestamp(float(current_time / 1e9)).replace(
            tzinfo=pytz.utc)

        # checking if we have a thermal model, and training if necessary.
        # _, err = self.check_thermal_model(building, zone)
        # if err is not None:
        #     return None, None, None, "No valid Thermal Model. (" + err + ")"
        # thermal_model, column_order = ThermalModel.THERMAL_MODELS[building][zone]
        # data_point = {
        #     "t_in": indoor_temperature,
        #     "action": action,
        #     "t_out": outside_temperature,
        #     "dt": get_window_in_sec(ThermalModel._INTERVAL),
        #     "t_prev": previous_indoor_temperature  # TODO t_last feature should be added to proto specs
        # }
        #
        # for iter_zone, iter_temp in other_zone_temperatures.items():
        #     if iter_zone != zone:
        #         data_point["temperature_zone_" + iter_zone] = iter_temp
        #
        # data_point = pd.DataFrame(data=[data_point], index=[current_time_datetime])[column_order]
        #
        # prediction = thermal_model.predict(data_point)

        prediction = [indoor_temperature + (action == 1) * 0.3 - (action == 2) * 0.3 + np.random.normal(0, 0.15)]

        if action == 1:
            if prediction[0] < indoor_temperature:
                prediction[0] = indoor_temperature + 0.5
        if action == 2:
            if prediction[0] > indoor_temperature:
                prediction[0] = indoor_temperature - 0.5
        if action == 0:
            prediction[0] = min(indoor_temperature + 0.35, prediction[0])
            prediction[0] = max(indoor_temperature - 0.35, prediction[0])


        return prediction[0], int(current_time + get_window_in_sec("5m") * 1e9), "F", None

        # return prediction[0], int(current_time + get_window_in_sec(ThermalModel._INTERVAL) * 1e9), "F", None
