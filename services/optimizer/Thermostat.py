import xbos_services_getter as xsg
import numpy as np
import pandas as pd
import datetime
import pytz

from DataManager.DataManager import DataManager


"""Thermostat class to model temperature change.
Note, set STANDARD fields to specify error for actions which do not have enough data for valid predictions. """
class DigitalTwin:
    STANDARD_MEAN = 0
    STANDARD_VAR = 0.05
    STANDARD_UNIT = "F"

    def __init__(self, building, zones, temperatures, start, end, window, last_temperatures=None, suppress_not_enough_data_error=False, non_controllable_data=None):
        self.temperatures = temperatures
        self.last_temperatures = last_temperatures
        self.indoor_temperature_prediction_stub = xsg.get_indoor_temperature_prediction_stub()
        self.error = {}
        self.building = building
        self.zones = zones
        self.start = start
        self.end = end
        self.DataManager = DataManager(building, zones, start, end, window, non_controllable_data)
        self.timesteps = {iter_zone: 0 for iter_zone in zones}

        for iter_zone in zones:
            for action in [xsg.NO_ACTION, xsg.HEATING_ACTION, xsg.COOLING_ACTION]:
                try:
                    END = datetime.datetime(year=2019, month=4, day=1).replace(
                        tzinfo=pytz.utc)  # datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
                    START = END - datetime.timedelta(days=365)
                    raise Exception("ERROR: Hack. Whoever sees this, yell at Daniel to get back to fixing the thermal model.")
                    # mean, var, unit = xsg.get_indoor_temperature_prediction_error(self.indoor_temperature_prediction_stub,
                    #                                                           building,
                    #                                                           iter_zone,
                    #                                                           action, START, END)
                except:
                    if not suppress_not_enough_data_error:
                        raise  Exception("ERROR: Tstat for building: '{0}' and zone: '{1}' did not receive error data from "
                          "indoor_temperature_prediction microservice for action: '{2}'.")

                    print("WARNING: Tstat for building: '{0}' and zone: '{1}' did not receive error data from "
                          "indoor_temperature_prediction microservice for action: '{2}' and is now using STANDARD error.".format(building, iter_zone, action))
                    mean, var, unit = DigitalTwin.STANDARD_MEAN, DigitalTwin.STANDARD_VAR, DigitalTwin.STANDARD_UNIT

                self.error[action] = {"mean": mean, "var": var}

    def next_temperature(self, action, zone):

        # data prep for updating temperatures
        curr_other_zone_temperatures = self.DataManager.all_zone_temperature_data.iloc[self.timesteps[zone]]
        for iter_zone_2 in self.zones:
            curr_other_zone_temperatures[iter_zone_2] = self.temperatures[iter_zone_2]

        for i in range(3):
            # new_temperature = xsg.get_indoor_temperature_prediction(self.DataManager.indoor_temperature_prediction_stub,
            #                                                         self.building,
            #                                                         zone,
            #                                                         self.start,
            #                                                         action,
            #                                                         self.temperatures[zone],
            #                                                         self.DataManager.outdoor_temperature.iloc[
            #                                                             self.timesteps[zone]],
            #                                                         self.last_temperatures[zone],
            #                                                         curr_other_zone_temperatures)[0]

            new_temperature = self.DataManager.get_indoor_temperature_prediction(self.building,
                                                                                    zone,
                                                                                    self.start,
                                                                                    action,
                                                                                    self.temperatures[zone],
                                                                                    self.DataManager.outdoor_temperature.iloc[self.timesteps[zone]],
                                                                                    self.last_temperatures[zone],
                                                                                    curr_other_zone_temperatures)[0]
            self.last_temperatures[zone] = self.temperatures[zone]
            self.temperatures[zone] = new_temperature

        self.temperatures[zone] += np.random.normal(self.error[action]["mean"], self.error[action]["var"])


        self.timesteps[zone] += 1
        return self.temperatures[zone]

    def reset(self, temperature, zone, last_temperature=None):
        self.temperatures[zone] = temperature
        self.last_temperatures[zone] = last_temperature
        self.timesteps[zone] = 0


class OutdoorThermostats:
    pass
