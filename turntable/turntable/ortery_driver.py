"""Ortery turntable driver."""
import re
import subprocess
from collections import namedtuple


class SSHOptions():
    """Options for SSH connection."""

    def __init__(self, user, host, password=None):
        """Initialize."""
        self.user = user
        self.host = host
        self.password = password

    def build_command(self, command):
        """Build a command."""
        password_prefix = ''
        if self.password:
            password_prefix = f"sshpass -p '{self.password}' "
        return f'{password_prefix}ssh -o StrictHostKeyChecking=no -o ' \
               f'LogLevel=QUIET {self.user}@{self.host} "{command}"'


def rwo(command, debug=False, ssh_opt=None):
    """Wrap subprocess.run to always capture output."""
    if ssh_opt:
        command = ssh_opt.build_command(command)
    if debug:
        print(command)
    proc = subprocess.run(command, capture_output=True, shell=True)
    output = proc.stdout.decode('utf-8')
    if debug:
        print(repr(output))
    return output


class UnexpectedOutputException(Exception):
    """Raised when the output is not as expected."""

    def __init__(self, command, output, m):
        """Initialize."""
        Exception.__init__(
            self,
            f'No matches. Command: {command}\nOutput: {output}' if not m else
            f'Matches: {m}\nCommand: {command}\nOutput: {output}')


def get_device_count(debug=False, ssh_opt=None):
    """Get the number of devices connected to this PC."""
    command = 'OTADCommand.exe get_device_count'
    output = rwo(command, debug, ssh_opt)
    m = re.search('^([0-9]+)\\r\\n$', output)
    if m is None or len(m.groups()) < 2:
        raise UnexpectedOutputException(command, output, m)
    return int(m.group(1))


class InvalidIdException(Exception):
    """Exception thrown when an invalid ID was passed, or device is offline."""

    def __init__(self, device_i):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i


class DeviceInfo():
    """Information of a device."""

    def __init__(self, product_name, device_i):
        """Initialize."""
        self.product_name = product_name
        self.device_i = device_i


def get_device_info(device_i, debug=False, ssh_opt=None):
    """Get the device information."""
    command = f'OTADCommand.exe get_device_info {device_i}'
    output = rwo(command, debug, ssh_opt)
    e = 'get_device_info :  command exec fail ( error code : 0x0040001)\r\n'
    if output == e:
        raise InvalidIdException(device_i)

    s = '^Product Name : ([A-Za-z0-9 ]+)\\r\\nDevice ID : ([0-9]+)\\r\\n'
    m = re.search(s, output)
    if m is None or len(m.groups()) < 3:
        raise UnexpectedOutputException(command, output, m)
    return DeviceInfo(m.group(1), m.group(2))


Command = namedtuple('Command', 'name value description')
command_dict = {
    12801: Command('otadDEVICE_COMMAND_CABLERLEASE_OFF',
                   12801,
                   'Shutter Release OFF'),
    12802: Command('otadDEVICE_COMMAND_CABLERLEASE_HALFWAY',
                   12802,
                   'Shutter Release Halfway (Focus)'),
    12803: Command('otadDEVICE_COMMAND_CABLERLEASE_COMPLETELY',
                   12803,
                   'Shutter Release Completely (Snap)'),
    13057: Command('otadDEVICE_COMMAND_TURNTABLE_STOP',
                   13057,
                   'Stop the turntable'),
    13058: Command('otadDEVICE_COMMAND_TURNTABLE_RELEASE',
                   13058,
                   'Release the motor of turntable'),
    16641: Command('otadDEVICE_PROPERTY_TURNTABLE_STATE',
                   16641,
                   'State of turntable')
    }


class UnknownCommand():
    """Null command."""

    pass


def get_command_desc(device_i, debug=False, ssh_opt=None):
    """Get a list of commands supported by the device."""
    cmd = f'OTADCommand.exe get_command_desc {device_i}'
    output = rwo(cmd, debug, ssh_opt)
    e = 'get_command_desc :  command exec fail ( error code : 0x0040001)\r\n'
    if output == e:
        raise InvalidIdException(device_i)

    command_ids = re.findall('([0-9]+)\r\n', output)
    return [command_dict.get(int(command_id), UnknownCommand())
            for command_id in command_ids]


Property = namedtuple('Property', 'name value description')
property_dict = {
    16641: Property('otadDEVICE_PROPERTY_TURNTABLE_STATE',
                    16641,
                    'State of turntable'),
    16643: Property('otadDEVICE_PROPERTY_TURNTABLE_TOTAL_STEPS',
                    16643,
                    'Total step of turntable')
    }


class UnknownProperty():
    """Null property."""

    pass


def get_property_desc(device_i, debug=False, ssh_opt=None):
    """Get a list of properties that can be read or set by the device."""
    cmd = f'OTADCommand.exe get_property_desc {device_i}'
    output = rwo(cmd, debug, ssh_opt)
    e = 'get_property_desc :  command exec fail ( error code : 0x0040001)\r\n'
    if output == e:
        raise InvalidIdException(device_i)

    property_ids = re.findall('([0-9]+)\r\n', output)
    return [property_dict.get(int(property_id), UnknownProperty())
            for property_id in property_ids]


class PropertyValueUnsupportedException(Exception):
    """Exception for when this property is not supported."""

    def __init__(self, device_i, property_id, data):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.property_id = property_id
        self.data = data


class SetPropertiesValueUnsupportedException(Exception):
    """Exception for when setting this property is not supported."""

    def __init__(self, device_i, properties, data):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.properties = properties
        self.data = data


class GetPropertyValueUnsupportedException(Exception):
    """Exception for when setting this property is not supported."""

    def __init__(self, device_i, property_id):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.property_id = property_id


class GetPropertyDeviceNotSupportPropertyException(Exception):
    """Exception for when setting this property is not supported."""

    def __init__(self, device_i, properties):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.properties = properties


def get_property_data(device_i, property_id, debug=False, ssh_opt=None):
    """Get the data for a specified property."""
    cmd = f'OTADCommand.exe get_property_data {device_i} {property_id}'
    responded = False
    while not responded:
        output = rwo(cmd, True, ssh_opt)
        if output == '':
            continue
        e = 'get_property_data :  command exec fail ( error code : 0x0040001)\r\n'  # noqa
        if output == e:
            raise InvalidIdException(device_i)
        e = 'get_property_data :  command exec fail ( error code : 0x004000a)\r\n'  # noqa
        if output == e:
            raise GetPropertyValueUnsupportedException(device_i, property_id)
        e = 'get_property_data :  command exec fail ( error code : 0x0040005)\r\n'  # noqa
        if output == e:
            raise GetPropertyDeviceNotSupportPropertyException(device_i,
                                                               property_id)
        m = re.search('^([0-9]+)', output)
        if m is None or len(m.groups()) < 1:
            raise UnexpectedOutputException(cmd, output, m)
        responded = True
    return int(m.group(1))


class SetPropertyValueUnsupportedException(Exception):
    """Exception for when setting this property is not supported."""

    def __init__(self, device_i, property_id, data):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.property_id = property_id
        self.data = data


class SetPropertyDeviceNotSupportException(Exception):
    """Exception for when setting this property is not supported."""

    def __init__(self, device_i, properties, data):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.properties = properties
        self.data = data


def set_property_data(device_i, property_id, data, debug=False, ssh_opt=None):
    """Set the data for a specified property."""
    if device_i is None:
        raise ValueError('device_i')
    if property_id is None:
        raise ValueError('property_id')
    if data is None:
        raise ValueError('data')
    cmd = f'OTADCommand.exe set_property_data {device_i} {property_id} {data}'
    output = rwo(cmd, debug, ssh_opt)
    e = 'set_property_data :  command exec fail ( error code : 0x0040001)\r\n'
    if output == e:
        raise InvalidIdException(device_i)
    e = 'set_property_data :  command exec fail ( error code : 0x004000a)\r\n'
    if output == e:
        raise SetPropertyValueUnsupportedException(device_i, property_id, data)
    e = 'set_property_data :  command exec fail ( error code : 0x0040005)\r\n'
    if output == e:
        raise SetPropertyDeviceNotSupportException(device_i, property_id, data)
    return True


class SetPropertyDeviceNotSupportPropertyException(Exception):
    """Exception for when setting this property is not supported."""

    def __init__(self, device_i, properties):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.properties = properties


def set_properties_data(device_i, properties, data, debug=False, ssh_opt=None):
    """Set properties on the device."""
    if type(device_i) is not int:
        raise ValueError('device_i needs to be an int')
    if type(properties) is not list:
        raise ValueError('device_i should be a list')
    if len(properties) == 0:
        raise ValueError('At least one property should be specified')
    if len(properties) > 20:
        raise ValueError('Maximum of 20 properties can be set at a time')
    cmd_builder = f'OTADCommand.exe set_properties_data {device_i} {data}'
    for prop in properties:
        cmd_builder += f' {prop}'
    output = rwo(cmd_builder, debug, ssh_opt)
    e = 'set_properties_data :  command exec fail ( error code : 0x0040001)\r\n'  # noqa
    if output == e:
        raise InvalidIdException(device_i)
    e = 'set_properties_data :  command exec fail ( error code : 0x004000a)\r\n'  # noqa
    if output == e:
        raise SetPropertiesValueUnsupportedException(
            device_i, properties, data)
    e = 'set_properties_data :  command exec fail ( error code : 0x0040005)\r\n'  # noqa
    if output == e:
        raise SetPropertyDeviceNotSupportPropertyException(
            device_i, properties, data)
    return True


class CommandUnsupportedException(Exception):
    """Exception for when setting this property is not supported."""

    def __init__(self, device_i, command):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.command = command


class CommandNotSupportedByDeviceException(Exception):
    """Exception for when setting this property is not supported."""

    def __init__(self, device_i, command):
        """Initialize."""
        Exception.__init__(self)
        self.device_i = device_i
        self.command = command


def send_command(device_i, command_id, debug=False, ssh_opt=None):
    """Send command to the device."""
    if type(device_i) is not int:
        raise ValueError('device_i needs to be an int')
    if type(command_id) is not int:
        raise ValueError('command_id needs to be an int')
    cmd = f'OTADCommand.exe send_command {device_i} {command_id}'
    output = rwo(cmd, debug, ssh_opt)
    e = 'send_command :  command exec fail ( error code : 0x0040001)\r\n'
    if output == e:
        raise InvalidIdException(device_i)
    e = 'send_command :  command exec fail ( error code : 0x004000a)\r\n'
    if output == e:
        raise CommandUnsupportedException(device_i, command_id)
    e = 'send_command :  command exec fail ( error code : 0x0040005)\r\n'
    if output == e:
        raise CommandNotSupportedByDeviceException(device_i, command_id)
    return True


SPEED_LOW = 0
SPEED_NORMAL = 1
SPEED_HIGH = 2

DIRECTION_CLOCKWISE = 0
DIRECTION_COUNTER_CLOCKWISE = 1


def turntable(device_i, speed, direction, step, debug=False, ssh_opt=None):
    """Turn."""
    if type(device_i) is not int:
        raise ValueError('device_i needs to be an int')
    if speed < 0 or speed > 2:
        raise ValueError('The range for speed is from 0 to 2')
    if direction != 0 and direction != 1:
        raise ValueError('The accepted values for direction are 0 and 1.')
    if step < 0 or step > 665535:
        raise ValueError('The range for step is from 0 to 665535')
    cmd = f'OTADCommand.exe turntable {device_i} {speed} {direction} {step}'
    output = rwo(cmd, debug, ssh_opt)
    e = 'turntable :  command exec fail ( error code : 0x0040001)\r\n'
    if output == e:
        raise InvalidIdException(device_i)
    return True
