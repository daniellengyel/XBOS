import time

import datetime
import pytz
import pandas as pd
import numpy as np

import xbos_services_getter as xsg
from .local_thermal_model.ThermalModel import ThermalModel


def check_data_zones(zones, data_dict, start, end, window, check_nan=True):
    for zone in zones:
        if zone not in data_dict:
            return "Is missing zone " + zone
        err = xsg.check_data(data_dict[zone], start, end, window, check_nan=check_nan)
        if err is not None:
            return err
    return None


"""Allows to easily retrieve all necessary data for doing Optimizations and Simulations.
Will get all data which is not found in the non_controallable_data argument."""
class DataManager:
    def __init__(self, building, zones, start, end, window, non_controllable_data={}):
        """Exposes:
            - self.comfortband
            - self.do_not_exceed
            - self.occupancy
            - self.outdoor_temperature
            - self.discomfort_stub
            - self.hvac_consumption
            - self.price
            - self.all_zone_temperatures: pd.df with columns being zone names and values being F temperatures

            - self.start
            - self.unix_start
            - self.end
            - self.unix_end
            - self.window

            - self.building
            - self.zones


        :param building:
        :param zones:
        :param start:
        :param end:
        :param window:
        :param non_controllable_data: possible keys:
                ["comfortband", "do_not_exceed", "occupancy", "outdoor_temperature"]
                for each key the value needs to be a dictionary with {zone: data} for all zones in self.zones.
                Outdoor temperature is just data since it is data for the whole building.
        """

        self.start = start
        self.unix_start = start.timestamp() * 1e9
        self.end = end
        self.unix_end = end.timestamp() * 1e9
        self.window = window  # timedelta string

        self.building = building
        self.zones = zones

        if non_controllable_data is None:
            non_controllable_data = {}
        # TODO add error checking. check that the right zones are given in non_controllable_data and that the start/end/window are right.

        # Documentation: All data here is in timeseries starting exactly at start and every step corresponds to one
        # interval. The end is not inclusive.

        # temperature band
        temperature_band_stub = xsg.get_temperature_band_stub()

        if "comfortband" not in non_controllable_data:
            self.comfortband = {
            iter_zone: xsg.get_comfortband(temperature_band_stub, self.building, iter_zone, self.start, self.end,
                                           self.window)
            for iter_zone in self.zones}
        else:
            self.comfortband = non_controllable_data["comfortband"]
        err = check_data_zones(self.zones, self.comfortband, start, end, window)
        if err is not None:
            raise Exception("Bad comfortband given. " + err)

        if "do_not_exceed" not in non_controllable_data:
            self.do_not_exceed = {
            iter_zone: xsg.get_do_not_exceed(temperature_band_stub, self.building, iter_zone, self.start, self.end,
                                             self.window)
            for iter_zone in self.zones}
        else:
            self.do_not_exceed = non_controllable_data["do_not_exceed"]
        err = check_data_zones(self.zones, self.do_not_exceed, start, end, window)
        if err is not None:
            raise Exception("Bad DoNotExceed given. " + err)

        # occupancy
        if "occupancy" not in non_controllable_data:
            occupancy_stub = xsg.get_occupancy_stub()
            self.occupancy = {
            iter_zone: xsg.get_occupancy(occupancy_stub, self.building, iter_zone, self.start, self.end, self.window)["occupancy"]
            for iter_zone in self.zones}
        else:
            self.occupancy = non_controllable_data["occupancy"]
        err = check_data_zones(self.zones, self.occupancy, start, end, window)
        if err is not None:
            raise Exception("Bad occupancy given. " + err)

        # outdoor temperatures
        if "outdoor_temperature" not in non_controllable_data:
            outdoor_historic_stub = xsg.get_outdoor_temperature_historic_stub()
            self.outdoor_temperature = xsg.get_preprocessed_outdoor_temperature(outdoor_historic_stub, self.building,
                                                                            self.start, self.end, self.window)["temperature"]
        else:
            self.outdoor_temperature = non_controllable_data["outdoor_temperature"]
        err = xsg.check_data(self.outdoor_temperature, start, end, window, check_nan=True)
        if err is not None:
            raise Exception("Bad outdoor temperature given. " + err)
        #         outdoor_prediction_channel = grpc.insecure_channel(OUTSIDE_PREDICTION)
        #         outdoor_prediction_stub = outdoor_temperature_prediction_pb2_grpc.OutdoorTemperatureStub(outdoor_prediction_channel)

        #         self.outdoor_temperatures = get_outside_temperature(
        #             outdoor_historic_stub, outdoor_prediction_stub, self.building, self.start, self.end, self.window)

        # discomfort channel
        # self.discomfort_stub = xsg.get_discomfort_stub(secure=False)

        # HVAC Consumption TODO ERROR CHECK?
        hvac_consumption_stub = xsg.get_hvac_consumption_stub()
        self.hvac_consumption = {iter_zone: xsg.get_hvac_consumption(hvac_consumption_stub, building, iter_zone)
                                 for iter_zone in self.zones}

        if "energy_price" not in non_controllable_data:
            price_stub = xsg.get_price_stub()
            self.energy_price = xsg.get_price(price_stub, building, "ENERGY", start, end, window)
        else:
            self.energy_price = non_controllable_data["energy_price"]
        err = xsg.check_data(self.energy_price, start, end, window, check_nan=True)
        if err is not None:
            raise Exception("Bad energy prices given. " + err)

        self.indoor_temperature_prediction_stub = xsg.get_indoor_temperature_prediction_stub()
        indoor_historic_stub = xsg.get_indoor_historic_stub()

        # TEMPORARY --------

        self.indoor_temperature_prediction = ThermalModel()

        # ------------

        # +++++++++++++ TODO other zone temps uncomment when wanting to use real thermal model and delete uncommented section
        #
        # # get indoor temperature for other zones.
        # if "all_zone_temperature_data" not in non_controllable_data:
        #     building_zone_names_stub = xsg.get_building_zone_names_stub()
        #     all_zones = xsg.get_zones(building_zone_names_stub, building)
        #     self.all_zone_temperature_data = {}
        #     for iter_zone in all_zones:
        #         # TODO there is an error with the indoor historic service where it doesn't return the full lenght of data.
        #         zone_temperature = xsg.get_indoor_temperature_historic(indoor_historic_stub, building, iter_zone, start, end + datetime.timedelta(seconds=xsg.get_window_in_sec(window)),
        #                                                                  window)
        #         assert zone_temperature['unit'].values[0] == "F"
        #         zone_temperature = zone_temperature["temperature"].squeeze()
        #         self.all_zone_temperature_data[iter_zone] = zone_temperature.interpolate("time")
        #     self.all_zone_temperature_data = pd.DataFrame(self.all_zone_temperature_data)
        # else:
        #     self.all_zone_temperature_data = non_controllable_data["all_zone_temperature_data"]
        # err = check_data_zones(zones, self.all_zone_temperature_data, start, end, window, check_nan=True)
        # if err is not None:
        #     if "Is missing zone" in err:
        #         raise Exception("Bad indoor temperature data given. " + err)
        #     else:
        #         for iter_zone in zones:
        #             err = xsg.check_data(self.all_zone_temperature_data[iter_zone], start, end, window, True)
        #             if "Nan values in data." in err:
        #                 self.all_zone_temperature_data[iter_zone][:] = 70 # TODO only doing this if interpolation above does not work because everything is nan
        #             else:
        #                 raise Exception("Bad indoor temperature data given. " + err)

        building_zone_names_stub = xsg.get_building_zone_names_stub()
        all_zones = xsg.get_zones(building_zone_names_stub, building)
        temp_pd = pd.Series(data=0, index = pd.date_range(start, end, freq=str(xsg.get_window_in_sec(window)) + "S"))
        self.all_zone_temperature_data = {iter_zone: temp_pd for iter_zone in all_zones}

        err = check_data_zones(zones, self.all_zone_temperature_data, start, end, window, check_nan=True)

        if err is not None:
            raise Exception("Bad indoor temperature data given. " + err)

        self.all_zone_temperature_data = pd.DataFrame(self.all_zone_temperature_data)

        # +++++++++++++




    def get_discomfort(self, building, temperature, temperature_low, temperature_high, occupancy):
        discomfort = max(
            temperature_low - temperature,
            temperature - temperature_high,
            0
        )
        return occupancy * discomfort

    def get_indoor_temperature_prediction(self, building,
                                             zone,
                                          current_time,
                                             action,
                                             temperature,
                                             outdoor_temperature,
                                             last_temperature,
                                             curr_other_zone_temperatures):
        current_time = current_time.replace(microsecond=0)

        current_time_unix = int(current_time.timestamp() * 1e9)

        if isinstance(curr_other_zone_temperatures, pd.DataFrame) or isinstance(curr_other_zone_temperatures, pd.Series):
            curr_other_zone_temperatures = curr_other_zone_temperatures.to_dict()

        prediction, returned_time, unit, err = self.indoor_temperature_prediction.prediction(building, zone, current_time_unix, action, temperature, last_temperature, outdoor_temperature, curr_other_zone_temperatures, "F")
        if err is not None:
            raise Exception(err)
        return prediction, returned_time, unit
