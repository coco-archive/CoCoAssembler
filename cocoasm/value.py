"""
Copyright (C) 2019-2020 Craig Thomas

This project uses an MIT style license - see LICENSE for details.
A Color Computer Assembler - see the README.md file for details.
"""
# I M P O R T S ###############################################################

import re

# C O N S T A N T S ###########################################################

# Pattern to recognize a hex value
HEX_REGEX = re.compile(
    r"^\$(?P<value>[0-9a-fA-F]+)"
)

# Pattern to recognize an integer value
INT_REGEX = re.compile(
    r"^(?P<value>[\d]+)"
)

# C L A S S E S  ##############################################################


class Value(object):
    """
    Represents a base value that can be retrieved as an integer or hex value
    string.
    """
    def __init__(self, value):
        self.int_value = 0
        self.parse_input(value)

    def parse_input(self, value):
        """
        Parses an input string value. Input strings are either integer values,
        or a hex value starting with $.

        :param value: the value to parse
        """
        data = HEX_REGEX.match(value)
        if data:
            if len(data.group("value")) > 4:
                raise ValueError("hex value length cannot exceed 4 characters")
            self.int_value = int(data.group("value"), 16)
            return

        data = INT_REGEX.match(value)
        if data:
            self.int_value = int(data.group("value"), 10)
            if self.int_value > 65535:
                raise ValueError("integer value cannot exceed 65535")
            return

        raise ValueError("supplied value is neither integer or hex value")

    def get_integer(self):
        """
        Returns an integer value for the object.

        :return: the integer value of the object
        """
        return self.int_value

    def get_hex_str(self):
        """
        Returns a hex string representation of the object.

        :return: the hex representation of the object
        """
        size = self.get_hex_length()
        size += 1 if size % 2 == 1 else 0
        format_specifier = "{{:0>{}X}}".format(size)
        return format_specifier.format(self.get_integer())

    def get_hex_length(self):
        """
        Returns the full length of the hex representation.

        :return: the full number of hex characters
        """
        return len(hex(self.int_value)[2:])

    def get_hex_byte_size(self):
        """
        Returns how many bytes are in the hex representation.

        :return: the number of hex bytes in the object
        """
        return int(self.get_hex_length() / 2)

# E N D   O F   F I L E #######################################################
