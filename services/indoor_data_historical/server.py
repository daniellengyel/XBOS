from concurrent import futures
import time
import grpc
import pymortar
import indoor_data_historical_pb2
import indoor_data_historical_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

import os, sys
from datetime import datetime
from rfc3339 import rfc3339
import pytz

INDOOR_DATA_HISTORICAL_HOST_ADDRESS = os.environ["INDOOR_DATA_HISTORICAL_HOST_ADDRESS"]

def _get_raw_modes(building, zone, pymortar_client, start, end, window_size, aggregation):
    """
    :param building:
    :param zone:
    :param pymortar_client:
    :param start: datetime, timezone aware, rfc3339
    :param end: datetime, timezone aware, rfc3339
    :param window_size: string with [s, m, h, d] classified in the end. e.g. "1s" for one second.
    :return:
    """
    thermostat_mode_query = """SELECT ?tstat ?status_point WHERE {
            ?tstat rdf:type brick:Thermostat .
            ?tstat bf:controls/bf:feeds <http://xbos.io/ontologies/%s#%s> .
            ?tstat bf:hasPoint ?status_point .
            ?status_point rdf:type brick:Thermostat_Mode_Command .
        };""" % (building, zone)

    # resp = pymortar_client.qualify([thermostat_mode_query]) Needed to get list of all sites

    thermostat_mode_view = pymortar.View(
        name="thermostat_mode_view",
        sites=[building],
        definition=thermostat_mode_query,
    )

    thermostat_mode_stream = pymortar.DataFrame(
        name="thermostat_mode",
        aggregation=aggregation,
        window=window_size,
        timeseries=[
            pymortar.Timeseries(
                view="thermostat_mode_view",
                dataVars=["?status_point"],
            )
        ]
    )

    request = pymortar.FetchRequest(
        sites=[building],
        views=[
            thermostat_mode_view
        ],
        dataFrames=[
            thermostat_mode_stream
        ],
        time=pymortar.TimeParams(
            start=rfc3339(start),
            end=rfc3339(end),
        )
    )

    thermostat_mode_data = pymortar_client.fetch(request)["thermostat_mode"]

    if thermostat_mode_data is None:
        return None, "did not fetch data from pymortar with query: %s" % thermostat_mode_query

    return thermostat_mode_data, None

def _get_raw_actions(building, zone, pymortar_client, start, end, window_size, aggregation):
    """
    TODO how to deal with windows in which two different actions are performed in given zone.
    Note: GETS THE MAX ACTION IN GIVEN INTERVAL.
    :param building:
    :param zone:
    :param pymortar_client:
    :param start: datetime, timezone aware, rfc3339
    :param end: datetime, timezone aware, rfc3339
    :param window_size: string with [s, m, h, d] classified in the end. e.g. "1s" for one second.
    :return:
    """
    thermostat_action_query = """SELECT ?tstat ?status_point WHERE {
            ?tstat rdf:type brick:Thermostat .
            ?tstat bf:controls/bf:feeds <http://xbos.io/ontologies/%s#%s> .
            ?tstat bf:hasPoint ?status_point .
            ?status_point rdf:type brick:Thermostat_Status .
        };""" % (building, zone)

    # resp = pymortar_client.qualify([thermostat_action_query]) Needed to get list of all sites

    thermostat_action_view = pymortar.View(
        name="thermostat_action_view",
        sites=[building],
        definition=thermostat_action_query,
    )

    thermostat_action_stream = pymortar.DataFrame(
        name="thermostat_action",
        aggregation=aggregation,
        window=window_size,
        timeseries=[
            pymortar.Timeseries(
                view="thermostat_action_view",
                dataVars=["?status_point"],
            )
        ]
    )

    request = pymortar.FetchRequest(
        sites=[building],
        views=[
            thermostat_action_view
        ],
        dataFrames=[
            thermostat_action_stream
        ],
        time=pymortar.TimeParams(
            start=rfc3339(start),
            end=rfc3339(end),
        )
    )

    thermostat_action_data = pymortar_client.fetch(request)["thermostat_action"]

    if thermostat_action_data is None:
        return None, "did not fetch data from pymortar with query: %s" % thermostat_action_query

    if len(thermostat_action_data.columns != 1):
        return None, "zero or more than one stream for given query: %s" % thermostat_action_query

    return thermostat_action_data, None

def _get_raw_indoor_temperatures(building, zone, pymortar_client, start, end, window_size, aggregation):
    """
    :param building:
    :param zone:
    :param pymortar_client:
    :param start: datetime, timezone aware, rfc3339
    :param end: datetime, timezone aware, rfc3339
    :param window_size:
    :return:
    """
    temperature_query = """SELECT ?tstat ?temp WHERE {
                ?tstat rdf:type brick:Thermostat .
                ?tstat bf:controls/bf:feeds <http://xbos.io/ontologies/%s#%s> .
                ?tstat bf:hasPoint ?temp .
                ?temp  rdf:type brick:Temperature_Sensor  .
            };""" % (building, zone)

    #resp = pymortar_client.qualify([temperature_query]) Need to get list of all sites

    temperature_view = pymortar.View(
        name="temperature_view",
        sites=[building],
        definition=temperature_query,
    )

    temperature_stream = pymortar.DataFrame(
        name="temperature",
        aggregation=aggregation,
        window=window_size,
        timeseries=[
            pymortar.Timeseries(
                view="temperature_view",
                dataVars=["?temp"],
            )
        ]
    )

    request = pymortar.FetchRequest(
        sites=[building],
        views=[
            temperature_view
        ],
        dataFrames=[
            temperature_stream
        ],
        time=pymortar.TimeParams(
            start=rfc3339(start),
            end=rfc3339(end),
        )
    )

    temperature_data = pymortar_client.fetch(request)["temperature"]

    if temperature_data is None:
        return None, "did not fetch data from pymortar with query: %s" % temperature_query

    return temperature_data, None

def _get_raw_temperature_bands(building, zone, pymortar_client, start, end, window_size, aggregation):
    """
    :param building:
    :param zone:
    :param pymortar_client:
    :param start: datetime, timezone aware, rfc3339
    :param end: datetime, timezone aware, rfc3339
    :param window_size:
    :return:
    """
    temperature_bands_query = """
        SELECT ?tstat ?heating_setpoint ?cooling_setpoint WHERE {
        ?tstat bf:controls/bf:feeds <http://xbos.io/ontologies/%s#%s> .
        ?tstat bf:hasPoint ?heating_setpoint .
        ?tstat bf:hasPoint ?cooling_setpoint .
        ?heating_setpoint rdf:type brick:Supply_Air_Temperature_Heating_Setpoint .
        ?cooling_setpoint rdf:type brick:Supply_Air_Temperature_Cooling_Setpoint
    };""" % (building, zone)

    temperature_bands_view = pymortar.View(
        name="temperature_bands_view",
        sites=[building],
        definition=temperature_bands_query,
    )

    temperature_bands_stream = pymortar.DataFrame(
        name="temperature_bands",
        aggregation=aggregation,
        window=window_size,
        timeseries=[
            pymortar.Timeseries(
                view="temperature_bands_view",
                dataVars=["?heating_setpoint", "?cooling_setpoint"],
            )
        ]
    )

    request = pymortar.FetchRequest(
        sites=[building],
        views=[
            temperature_bands_view
        ],
        dataFrames=[
            temperature_bands_stream
        ],
        time=pymortar.TimeParams(
            start=rfc3339(start),
            end=rfc3339(end),
        )
    )

    temperature_bands_data = pymortar_client.fetch(request)["temperature_bands"]

    if temperature_bands_data is None:
        return None, "did not fetch data from pymortar with query: %s" % temperature_bands_query

    return temperature_bands_data, None


def get_raw_temperature_bands(request, pymortar_client):
    """Returns temperature setpoints for the given request or None."""
    print("received request:", request.building, request.zone, request.start, request.end, request.window, request.aggregation)
    duration = get_window_in_sec(request.window)

    unit = "F" # we will keep the outside temperature in fahrenheit for now.

    request_length = [len(request.building), len(request.zone), request.start, request.end,
                      duration, request.aggregation]
    if any(v == 0 for v in request_length):
        return None, "invalid request, empty params"
    if request.end > int(time.time() * 1e9):
        return None, "invalid request, end date is in the future."
    if request.start >= request.end:
        return None, "invalid request, start date is after end date."
    if request.start < 0 or request.end < 0:
        return None, "invalid request, negative dates"
    if request.start + (duration * 1e9) > request.end:
        return None, "invalid request, start date + window is greater than end date"

    pymortar_objects = {
        'MEAN': pymortar.MEAN,
        'MAX': pymortar.MAX,
        'MIN': pymortar.MIN,
        'COUNT': pymortar.COUNT,
        'SUM': pymortar.SUM,
        'RAW': pymortar.RAW
    }

    agg = pymortar_objects.get(request.aggregation, 'ERROR')
    if agg == 'ERROR':
        return None, "invalid aggregation parameter"

    start_datetime = datetime.utcfromtimestamp(float(request.start / 1e9)).replace(tzinfo=pytz.utc)
    end_datetime = datetime.utcfromtimestamp(float(request.end / 1e9)).replace(tzinfo=pytz.utc)

    temperature_bands_data, err = _get_raw_temperature_bands(request.building, request.zone, pymortar_client,
                                                    start_datetime,
                                                    end_datetime,
                                                    request.window,
                                                    agg)

    if temperature_bands_data is None:
        return [indoor_data_historical_pb2.Setpoint()], "No data received from database."

    setpoints = []

    if len(temperature_bands_data.columns != 2):
        return None, "zero or more than two streams for given request: "

    for index, row in temperature_bands_data.iterrows():
        setpoints.append(indoor_data_historical_pb2.Setpoint(time=int(index.timestamp() * 1e9), temperature_low=row.iloc[1], temperature_high=row.iloc[0], unit=unit))

    return setpoints, None

# TODO Make sure we don't include NONE values in the returned points.
def get_raw_indoor_temperatures(request, pymortar_client):
    """Returns temperatures for the given request or None."""
    print("received temperature request:", request.building, request.zone, request.start, request.end, request.window, request.aggregation)
    duration = get_window_in_sec(request.window)

    unit = "F" # we will keep the outside temperature in fahrenheit for now.

    request_length = [len(request.building), len(request.zone), request.start, request.end,
                      duration, request.aggregation]
    if any(v == 0 for v in request_length):
        return None, "invalid request, empty params"
    if request.end > int(time.time() * 1e9):
        return None, "invalid request, end date is in the future."
    if request.start >= request.end:
        return None, "invalid request, start date is after end date."
    if request.start < 0 or request.end < 0:
        return None, "invalid request, negative dates"
    if request.start + (duration * 1e9) > request.end:
        return None, "invalid request, start date + window is greater than end date"

    pymortar_objects = {
        'MEAN': pymortar.MEAN,
        'MAX': pymortar.MAX,
        'MIN': pymortar.MIN,
        'COUNT': pymortar.COUNT,
        'SUM': pymortar.SUM,
        'RAW': pymortar.RAW
    }

    agg = pymortar_objects.get(request.aggregation, 'ERROR')
    if agg == 'ERROR':
        return None, "invalid aggregation parameter"

    start_datetime = datetime.utcfromtimestamp(float(request.start / 1e9)).replace(tzinfo=pytz.utc)
    end_datetime = datetime.utcfromtimestamp(float(request.end / 1e9)).replace(tzinfo=pytz.utc)

    raw_indoor_temperature_data, err = _get_raw_indoor_temperatures(request.building, request.zone, pymortar_client,
                                                    start_datetime,
                                                    end_datetime,
                                                    request.window,
                                                    agg)
    temperatures = []

    if raw_indoor_temperature_data is None:
        return [indoor_data_historical_pb2.TemperaturePoint()], "No data received from database."

    if len(raw_indoor_temperature_data.columns != 1):
        return None, "zero or more than one stream for given request"

    for index, temp in raw_indoor_temperature_data.iterrows():
        temperatures.append(indoor_data_historical_pb2.TemperaturePoint(time=int(index.timestamp() * 1e9), temperature=temp, unit=unit))

    return temperatures, None

def get_raw_modes(request, pymortar_client):
    """Returns modes for the given request or None."""
    print("received mode request:", request.building, request.zone, request.start, request.end, request.window, request.aggregation)
    duration = get_window_in_sec(request.window)

    request_length = [len(request.building), len(request.zone), request.start, request.end,
                      duration, request.aggregation]

    if any(v == 0 for v in request_length):
        return None, "invalid request, empty params"
    if request.end > int(time.time() * 1e9):
        return None, "invalid request, end date is in the future."
    if request.start >= request.end:
        return None, "invalid request, start date is after end date."
    if request.start < 0 or request.end < 0:
        return None, "invalid request, negative dates"
    if request.start + (duration * 1e9) > request.end:
        return None, "invalid request, start date + window is greater than end date"

    pymortar_objects = {
        'MEAN': pymortar.MEAN,
        'MAX': pymortar.MAX,
        'MIN': pymortar.MIN,
        'COUNT': pymortar.COUNT,
        'SUM': pymortar.SUM,
        'RAW': pymortar.RAW
    }

    agg = pymortar_objects.get(request.aggregation, 'ERROR')
    if agg == 'ERROR':
        return None, "invalid aggregation parameter"

    start_datetime = datetime.utcfromtimestamp(float(request.start / 1e9)).replace(tzinfo=pytz.utc)
    end_datetime = datetime.utcfromtimestamp(float(request.end / 1e9)).replace(tzinfo=pytz.utc)


    raw_mode_data, err = _get_raw_modes(request.building, request.zone, pymortar_client,
                                                    start_datetime,
                                                    end_datetime,
                                                    request.window,
                                                    agg)

    modes = []

    if raw_mode_data is None:
        return [indoor_data_historical_pb2.ModePoint()], "No data received from database."

    if len(raw_mode_data.columns != 1):
        return None, "zero or more than one stream for given query"

    for index, mode in raw_mode_data.iterrows():
        modes.append(indoor_data_historical_pb2.ModePoint(time=int(index.timestamp() * 1e9), mode=float(mode.values))) # TODO mode being int will be a problem.

    return modes, None



def get_raw_actions(request, pymortar_client):
    """Returns actions for the given request or None."""
    print("received action request:", request.building, request.zone, request.start, request.end, request.window, request.aggregation)
    duration = get_window_in_sec(request.window)

    request_length = [len(request.building), len(request.zone), request.start, request.end,
                      duration, request.aggregation]

    if any(v == 0 for v in request_length):
        return None, "invalid request, empty params"
    if request.end > int(time.time() * 1e9):
        return None, "invalid request, end date is in the future."
    if request.start >= request.end:
        return None, "invalid request, start date is after end date."
    if request.start < 0 or request.end < 0:
        return None, "invalid request, negative dates"
    if request.start + (duration * 1e9) > request.end:
        return None, "invalid request, start date + window is greater than end date"

    pymortar_objects = {
        'MEAN': pymortar.MEAN,
        'MAX': pymortar.MAX,
        'MIN': pymortar.MIN,
        'COUNT': pymortar.COUNT,
        'SUM': pymortar.SUM,
        'RAW': pymortar.RAW
    }

    agg = pymortar_objects.get(request.aggregation, 'ERROR')
    if agg == 'ERROR':
        return None, "invalid aggregation parameter"

    start_datetime = datetime.utcfromtimestamp(float(request.start / 1e9)).replace(tzinfo=pytz.utc)
    end_datetime = datetime.utcfromtimestamp(float(request.end / 1e9)).replace(tzinfo=pytz.utc)


    raw_action_data, err = _get_raw_actions(request.building, request.zone, pymortar_client,
                                                    start_datetime,
                                                    end_datetime,
                                                    request.window,
                                                    agg)

    actions = []

    if raw_action_data is None:
        return [indoor_data_historical_pb2.ActionPoint()], "No data received from database."

    for index, action in raw_action_data.iterrows():
        actions.append(indoor_data_historical_pb2.ActionPoint(time=int(index.timestamp() * 1e9), action=float(action.values))) # TODO action being int will be a problem.

    return actions, None

def get_window_in_sec(s):
    """Returns number of seconds in a given duration or zero if it fails.
       Supported durations are seconds (s), minutes (m), hours (h), and days(d)."""
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    try:
        return int(float(s[:-1])) * seconds_per_unit[s[-1]]
    except:
        return 0

class IndoorDataHistoricalServicer(indoor_data_historical_pb2_grpc.IndoorDataHistoricalServicer):
    def __init__(self):
        self.pymortar_client = pymortar.Client()

    def GetRawTemperatures(self, request, context):
        """A simple RPC.

        Sends the indoor temperature for a given HVAC zone, within a timeframe (start, end), and a requested window
        An error is returned if there are no temperatures for the given request
        """
        raw_temperatures, error = get_raw_indoor_temperatures(request, self.pymortar_client)
        if raw_temperatures is None:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(error)
            return indoor_data_historical_pb2.TemperaturePoint()
        elif error is not None:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(error)

        for temperature in raw_temperatures:
            yield temperature

    def GetRawTemperatureBands(self, request, context):
        """A simple RPC.

        Sends the indoor heating and cooling setpoints for a given HVAC zone, within a timeframe (start, end), and a requested window
        An error is returned if there are no setpoints for the given request
        """
        raw_temperature_bands, error = get_raw_temperature_bands(request, self.pymortar_client)
        if raw_temperature_bands is None:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(error)
            return indoor_data_historical_pb2.Setpoint()
        elif error is not None:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(error)

        for setpoint in raw_temperature_bands:
            yield setpoint

    def GetRawActions(self, request, context):
        """A simple RPC.

         Sends the indoor action for a given HVAC Zone, within a timeframe (start, end), and a requested window
         An error is returned if there are no actions for the given request
         """
        raw_actions, error = get_raw_actions(request, self.pymortar_client)
        if raw_actions is None:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(error)
            return indoor_data_historical_pb2.ActionPoint()
        elif error is not None:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(error)

        for action in raw_actions:
            yield action

    def GetRawModes(self, request, context):
        """A simple RPC.

         Sends the indoor mode for a given HVAC Zone, within a timeframe (start, end), and a requested window
         An error is returned if there are no modes for the given request
         """
        raw_modes, error = get_raw_modes(request, self.pymortar_client)
        if raw_modes is None:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(error)
            return indoor_data_historical_pb2.ModePoint()
        elif error is not None:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(error)

        for mode in raw_modes:
            yield mode

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    indoor_data_historical_pb2_grpc.add_IndoorDataHistoricalServicer_to_server(IndoorDataHistoricalServicer(), server)
    server.add_insecure_port(INDOOR_DATA_HISTORICAL_HOST_ADDRESS)
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
