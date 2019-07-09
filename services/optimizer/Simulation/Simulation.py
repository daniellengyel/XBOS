import time

import datetime
import pytz
import calendar
import itertools
import pandas as pd

import datetime
import sys

import numpy as np
import os
import pandas as pd
import pytz


import xbos_services_getter as xsg

from Optimizers.MPC.MPC import MPC
from Optimizers.MPC.MPC import Node
from DataManager.DataManager import DataManager
from Thermostat import DigitalTwin


# Simulation Class for MPC. Stops simulation when the current time is equal to the end.
class SimulationMPC():

    def __init__(self, building, zones, lambda_val, start, end, forecasting_horizon, window, tstats, non_contrallable_data=None):
        """

        :param building:
        :param zones:
        :param lambda_val:
        :param start: datetime with timezone
        :param end: datetime with timezone
        :param forecasting_horizon:
        :param window:
        :param tstats:
        :param non_contrallable_data:
        """
        assert xsg.get_window_in_sec(forecasting_horizon) % xsg.get_window_in_sec(window) == 0

        self.building = building
        self.zones = zones
        self.window = window
        self.lambda_val = lambda_val

        self.forecasting_horizon = forecasting_horizon
        self.delta_forecasting_horizon = datetime.timedelta(seconds=xsg.get_window_in_sec(forecasting_horizon))

        self.delta_window = datetime.timedelta(seconds=xsg.get_window_in_sec(window))

        # Simulation end is when current_time reaches end and end will become the end of our data.
        self.simulation_end = end
        end += self.delta_forecasting_horizon

        self.DataManager = DataManager(building, zones, start, end, window, non_contrallable_data)

        self.DigitalTwin = DigitalTwin  # dictionary of simulator object with key zone. has functions: current_temperature, next_temperature(action)

        self.current_time = start
        self.current_time_step = 0
        self.total_steps = (self.simulation_end - start)/self.delta_window

        self.actions = {iter_zone: [] for iter_zone in self.zones} # {zone: [ints]}
        self.temperatures = {iter_zone: [self.DigitalTwin.temperatures[iter_zone]] for iter_zone in zones} # {zone: [floats]}


    def step(self):

        # call
        start_mpc = self.current_time
        end_mpc = self.current_time + self.delta_forecasting_horizon
        non_controllable_data = {
            "comfortband": {iter_zone: self.DataManager.comfortband[iter_zone].loc[start_mpc:end_mpc] for iter_zone in self.zones},
            "do_not_exceed": {iter_zone: self.DataManager.do_not_exceed[iter_zone].loc[start_mpc:end_mpc] for iter_zone in self.zones},
            "occupancy": {iter_zone: self.DataManager.occupancy[iter_zone].loc[start_mpc:end_mpc] for iter_zone in self.zones},
            "outdoor_temperature": self.DataManager.outdoor_temperature.loc[start_mpc:end_mpc],
            "all_zone_temperature_data": self.DataManager.all_zone_temperature_data.loc[start_mpc:end_mpc]
        }

        op = MPC(self.building, self.zones, start_mpc, end_mpc, self.window, self.lambda_val, non_controllable_data=non_controllable_data,
                 debug=False)

        root = Node(self.DigitalTwin.temperatures, 0)

        root = op.shortest_path(root)
        best_action = op.g.node[root]["best_action"]


        # given the actions, update simulation of temperature.
        # increment time

        self.current_time += self.delta_window
        self.current_time_step += 1

        for iter_zone in self.zones:
            # advances temperature and saves it
            self.temperatures[iter_zone].append(self.DigitalTwin.next_temperature(best_action[iter_zone], iter_zone))
            self.actions[iter_zone].append(best_action[iter_zone])

        return root

    def run(self):
        while self.current_time < self.simulation_end:
            self.step()
            print("Percent done", 100 * self.current_time_step/float(self.total_steps))

            print(self.actions)
            print(self.temperatures)



if __name__ == "__main__":
    forecasting_horizon = "1h"

    # end = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) - datetime.timedelta(
    #     seconds=xsg.get_window_in_sec(forecasting_horizon))
    # end = end.replace(microsecond=0)
    # start = end - datetime.timedelta(hours=6)
    start = datetime.datetime(year=2019, month=1, day=1, hour=8).replace(tzinfo=pytz.utc)
    end = start + datetime.timedelta(hours=24)

    print(start)
    print(start.timestamp())
    building = "avenal-animal-shelter"
    zones = ["hvac_zone_shelter_corridor"]
    window = "15m"
    lambda_val = 0.995
    DigitalTwin = DigitalTwin(building, zones,
                              {iter_zone: 86 for iter_zone in
                               zones}, start, end, window,
                              last_temperatures={iter_zone: 80 for
                                                 iter_zone in zones},
                              suppress_not_enough_data_error=True)

    simulation = SimulationMPC(building, zones, lambda_val, start, end, forecasting_horizon, window, DigitalTwin)

    import pickle
    t = time.time()
    simulation.run()
    print(time.time() - t)
    print(simulation.actions)
    print(simulation.temperatures)
    with open("sim_res.pkl", "wb") as f:
        pickle.dump(simulation, f)
