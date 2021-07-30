import rclpy
import ortery_driver as driver
from rclpy.node import Node
from turntable_srvs.msg import CommandDesc
from turntable_srvs.srv import GetDeviceCount, GetDeviceInfo, GetCommandDescs


def map_ortery_command_desc_to_ros_type(ocd):
    desc = CommandDesc()
    desc.name = ocd.name
    desc.value = ocd.value
    desc.description = ocd.description
    return desc


class TurntableNode(Node):
    def __init__(self):
        self.get_device_count = self.create_service(
                                    GetDeviceCount,
                                    'get_device_count',
                                    self.get_device_count_callback)
        self.get_device_info =  self.create_service(
                                    GetDeviceInfo,
                                    'get_device_info',
                                    self.get_device_info_callback)
        self.get_command_desc =  self.create_service(
                                    GetCommandDesc,
                                    'get_command_desc',
                                    self.get_command_desc_callback)
        
    def get_device_count_callback(self, request, response):
        response.count = driver.get_device_count()
        return response

    def get_device_info_callback(self, request, response):
        try:
            device_info = driver.get_device_info(request.id)
            response.product_name = device_info.product_name
            response.device_id = device_info.device_id
            response.success = True
        except InvalidIdException:
            response.success = False

        return response

    def get_command_desc_callback(self, request, response):
        try:
            command_descs = driver.get_command_desc(request.id)
            response.command_descs = [
                map_ortery_command_desc_to_ros_type(command_desc)
                for command_desc in command_descs]
            response.success = True
        except InvalidIdException:
            response.success = False
        return response


def main(args=None):
    rclpy.init(args=args)

    turntable_node = TurntableNode()

    rclpy.spin(turntable_node)

    turntable_node.destroy_node()

    rclpy.shutdown()


if __name__ == '__main__':
    main()
