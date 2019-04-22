# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
import grpc

import optimizer_pb2 as optimizer__pb2


class OptimizerStub(object):
  """The optimizer service definition.
  """

  def __init__(self, channel):
    """Constructor.

    Args:
      channel: A grpc.Channel.
    """
    self.GetMPCOptimization = channel.unary_unary(
        '/outdoor_temperature_historical.Optimizer/GetMPCOptimization',
        request_serializer=optimizer__pb2.MPCOptimizationRequest.SerializeToString,
        response_deserializer=optimizer__pb2.Reply.FromString,
        )


class OptimizerServicer(object):
  """The optimizer service definition.
  """

  def GetMPCOptimization(self, request, context):
    """A simple RPC.

    Get the optimization of the MPC
    """
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')


def add_OptimizerServicer_to_server(servicer, server):
  rpc_method_handlers = {
      'GetMPCOptimization': grpc.unary_unary_rpc_method_handler(
          servicer.GetMPCOptimization,
          request_deserializer=optimizer__pb2.MPCOptimizationRequest.FromString,
          response_serializer=optimizer__pb2.Reply.SerializeToString,
      ),
  }
  generic_handler = grpc.method_handlers_generic_handler(
      'outdoor_temperature_historical.Optimizer', rpc_method_handlers)
  server.add_generic_rpc_handlers((generic_handler,))
