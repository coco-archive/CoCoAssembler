"""
Copyright (C) 2019-2020 Craig Thomas

This project uses an MIT style license - see LICENSE for details.
A Color Computer Assembler - see the README.md file for details.
"""
# I M P O R T S ###############################################################

import re

from abc import ABC, abstractmethod
from copy import copy
from enum import Enum

from cocoasm.values import NoneValue, ValueType, AddressValue, Value, NumericValue
from cocoasm.instruction import CodePackage

# C O N S T A N T S ###########################################################

# Pattern to recognize an immediate value
IMMEDIATE_REGEX = re.compile(
    r"^#(?P<value>.*)"
)

# Pattern to recognize a direct value
DIRECT_REGEX = re.compile(
    r"^<(?P<value>.*)"
)

# Pattern to recognize an extended value
EXTENDED_REGEX = re.compile(
    r"^>(?P<value>.*)"
)

# Pattern to recognize an indexed value
EXTENDED_INDIRECT_REGEX = re.compile(
    r"^\[(?P<value>.*)\]"
)

# Patten to recognize an expression
EXPRESSION_REGEX = re.compile(
    r"^(?P<left>[$]*[\d\w]+)(?P<operation>[+\-/*])(?P<right>[$]*[\d\w]+)$"
)

# Pattern to recognize invalid characters in an UnknownOperand
UNKNOWN_REGEX = re.compile(
    r","
)

# Recognized register names
REGISTERS = ["A", "B", "D", "X", "Y", "U", "S", "CC", "DP", "PC"]

# C L A S S E S ###############################################################


class OperandType(Enum):
    """
    The OperandType enumeration stores what kind of operand we have parsed.
    """
    UNKNOWN = 0
    INHERENT = 1
    IMMEDIATE = 2
    INDEXED = 3
    EXTENDED_INDIRECT = 4
    EXTENDED = 5
    DIRECT = 6
    RELATIVE = 7
    SYMBOL = 8
    EXPRESSION = 9
    PSEUDO = 10
    SPECIAL = 11


class Operand(ABC):
    def __init__(self, instruction, value=None):
        self.type = OperandType.UNKNOWN
        self.operand_string = ""
        self.instruction = instruction
        self.requires_resolution = False
        self.value = value if value else NoneValue(None)
        self.left = NoneValue(None)
        self.right = NoneValue(None)
        self.operation = ""

    @classmethod
    def create_from_str(cls, operand_string, instruction):
        try:
            return PseudoOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return SpecialOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return RelativeOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return InherentOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return ImmediateOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return DirectOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return ExtendedOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return ExtendedIndexedOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return IndexedOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return ExpressionOperand(operand_string, instruction)
        except ValueError:
            pass

        try:
            return UnknownOperand(operand_string, instruction)
        except ValueError:
            pass

        raise ValueError("[{}] unknown operand type".format(operand_string))

    def is_type(self, operand_type):
        """
        Returns True if the type of this operand class is the type being compared.

        :param operand_type: the OperandType to check
        :return: True if the OperandType values match, False otherwise
        """
        return self.type == operand_type

    def resolve_symbols(self, symbol_table):
        """
        Given a symbol table, searches the operands for any symbols, and resolves
        them with values from the symbol table. Returns a (possibly) new Operand
        class type as a result of symbol resolution.

        :param symbol_table: the symbol table to search
        :return: self, or a new Operand class type with a resolved value
        """
        if self.is_type(OperandType.EXPRESSION):
            return self.resolve_expression(symbol_table)

        if not self.value.is_type(ValueType.SYMBOL):
            return self

        symbol = self.get_symbol(self.value.ascii(), symbol_table)

        if symbol.is_type(ValueType.ADDRESS):
            self.value = AddressValue(symbol.int)
            if self.type == OperandType.UNKNOWN:
                return ExtendedOperand(self.operand_string, self.instruction, value=self.value)
            return self

        if symbol.is_type(ValueType.NUMERIC):
            self.value = copy(symbol)
            if self.value.hex_len() == 2:
                return DirectOperand(self.operand_string, self.instruction, value=self.value)
            return ExtendedOperand(self.operand_string, self.instruction, value=self.value)

    def resolve_expression(self, symbol_table):
        """
        Attempts to resolve the expression contained in the operand using the
        symbol table supplied. Returns a (possibly) new Operand class type as a
        result of symbol resolution.

        :param symbol_table: the symbol table to use for resolution
        :return: self, or a new Operand class type with a resolved value
        """
        if self.left.is_type(ValueType.SYMBOL):
            self.left = self.get_symbol(self.left.ascii(), symbol_table)

        if self.right.is_type(ValueType.SYMBOL):
            self.right = self.get_symbol(self.right.ascii(), symbol_table)

        if self.right.is_type(ValueType.NUMERIC) and self.left.is_type(ValueType.NUMERIC):
            left = self.left.int
            right = self.right.int
            if self.operation == "+":
                self.value = NumericValue("{}".format(left + right))
            if self.operation == "-":
                self.value = NumericValue("{}".format(left - right))
            if self.operation == "*":
                self.value = NumericValue("{}".format(int(left * right)))
            if self.operation == "/":
                self.value = NumericValue("{}".format(int(left / right)))
            if self.value.hex_len() == 2:
                return DirectOperand(self.operand_string, self.instruction, value=self.value)
            return ExtendedOperand(self.operand_string, self.instruction, value=self.value)

        raise ValueError("[{}] unresolved expression".format(self.operand_string))

    @staticmethod
    def get_symbol(symbol_label, symbol_table):
        if symbol_label not in symbol_table:
            raise ValueError("[{}] not in symbol table".format(symbol_label))
        return symbol_table[symbol_label]

    @abstractmethod
    def translate(self):
        """
        Using information contained within the instruction, translate the operand,
        and return a code package containing the equivalent machine code information.

        :return: a CodePackage containing the translated instruction
        """


class UnknownOperand(Operand):
    def __init__(self, operand_string, instruction, value=None):
        super().__init__(instruction)
        self.operand_string = operand_string
        if value:
            self.value = value
            return
        if UNKNOWN_REGEX.search(operand_string):
            raise ValueError("[{}] invalid operand".format(operand_string))
        try:
            self.value = Value.create_from_str(operand_string, instruction)
        except ValueError:
            self.value = NoneValue()

    def translate(self):
        return CodePackage(additional=self.value)


class PseudoOperand(Operand):
    def __init__(self, operand_string, instruction):
        super().__init__(instruction)
        self.operand_string = operand_string
        self.type = OperandType.PSEUDO
        if not instruction.is_pseudo:
            raise ValueError("[{}] is not a pseudo instruction".format(instruction.mnemonic))
        self.value = Value.create_from_str(operand_string, instruction)

    def resolve_symbols(self, symbol_table):
        return self

    def translate(self):
        if self.instruction.mnemonic == "FCB":
            return CodePackage(additional=self.value, size=1)

        if self.instruction.mnemonic == "FDB":
            return CodePackage(additional=NumericValue(self.value.int, size_hint=4), size=2)

        if self.instruction.mnemonic == "RMB":
            return CodePackage(additional=NumericValue(0, size_hint=self.value.int*2), size=self.value.int)

        if self.instruction.mnemonic == "ORG":
            return CodePackage(address=self.value)

        if self.instruction.mnemonic == "FCC":
            return CodePackage(additional=self.value, size=self.value.byte_len())

        return CodePackage()


class SpecialOperand(Operand):
    def __init__(self, operand_string, instruction):
        super().__init__(instruction)
        self.operand_string = operand_string
        self.type = OperandType.SPECIAL
        if not instruction.is_special:
            raise ValueError("[{}] is not a special instruction".format(instruction.mnemonic))

    def resolve_symbols(self, symbol_table):
        return self

    def translate(self):
        code_pkg = CodePackage()
        code_pkg.op_code = NumericValue(self.instruction.mode.imm)
        code_pkg.size = self.instruction.mode.imm_sz
        code_pkg.post_byte = 0x00

        if self.instruction.mnemonic == "PSHS" or self.instruction.mnemonic == "PULS":
            if not self.operand_string:
                raise ValueError("one or more registers must be specified")

            registers = self.operand_string.split(",")
            for register in registers:
                if register not in REGISTERS:
                    raise ValueError("[{}] unknown register".format(register))

                code_pkg.post_byte |= 0x06 if register == "D" else 0x00
                code_pkg.post_byte |= 0x01 if register == "CC" else 0x00
                code_pkg.post_byte |= 0x02 if register == "A" else 0x00
                code_pkg.post_byte |= 0x04 if register == "B" else 0x00
                code_pkg.post_byte |= 0x08 if register == "DP" else 0x00
                code_pkg.post_byte |= 0x10 if register == "X" else 0x00
                code_pkg.post_byte |= 0x20 if register == "Y" else 0x00
                code_pkg.post_byte |= 0x40 if register == "U" else 0x00
                code_pkg.post_byte |= 0x80 if register == "PC" else 0x00

        if self.instruction.mnemonic == "EXG" or self.instruction.mnemonic == "TFR":
            registers = self.operand_string.split(",")
            if len(registers) != 2:
                raise ValueError("[{}] requires exactly 2 registers".format(self.instruction.mnemonic))

            if registers[0] not in REGISTERS:
                raise ValueError("[{}] unknown register".format(registers[0]))

            if registers[1] not in REGISTERS:
                raise ValueError("[{}] unknown register".format(registers[1]))

            code_pkg.post_byte |= 0x00 if registers[0] == "D" else 0x00
            code_pkg.post_byte |= 0x00 if registers[1] == "D" else 0x00

            code_pkg.post_byte |= 0x10 if registers[0] == "X" else 0x00
            code_pkg.post_byte |= 0x01 if registers[1] == "X" else 0x00

            code_pkg.post_byte |= 0x20 if registers[0] == "Y" else 0x00
            code_pkg.post_byte |= 0x02 if registers[1] == "Y" else 0x00

            code_pkg.post_byte |= 0x30 if registers[0] == "U" else 0x00
            code_pkg.post_byte |= 0x03 if registers[1] == "U" else 0x00

            code_pkg.post_byte |= 0x40 if registers[0] == "S" else 0x00
            code_pkg.post_byte |= 0x04 if registers[1] == "S" else 0x00

            code_pkg.post_byte |= 0x50 if registers[0] == "PC" else 0x00
            code_pkg.post_byte |= 0x05 if registers[1] == "PC" else 0x00

            code_pkg.post_byte |= 0x80 if registers[0] == "A" else 0x00
            code_pkg.post_byte |= 0x08 if registers[1] == "A" else 0x00

            code_pkg.post_byte |= 0x90 if registers[0] == "B" else 0x00
            code_pkg.post_byte |= 0x09 if registers[1] == "B" else 0x00

            code_pkg.post_byte |= 0xA0 if registers[0] == "CC" else 0x00
            code_pkg.post_byte |= 0x0A if registers[1] == "CC" else 0x00

            code_pkg.post_byte |= 0xB0 if registers[0] == "DP" else 0x00
            code_pkg.post_byte |= 0x0B if registers[1] == "DP" else 0x00

            if code_pkg.post_byte not in \
                    [
                        0x01, 0x10, 0x02, 0x20, 0x03, 0x30, 0x04, 0x40,
                        0x05, 0x50, 0x12, 0x21, 0x13, 0x31, 0x14, 0x41,
                        0x15, 0x51, 0x23, 0x32, 0x24, 0x42, 0x25, 0x52,
                        0x34, 0x43, 0x35, 0x53, 0x45, 0x54, 0x89, 0x98,
                        0x8A, 0xA8, 0x8B, 0xB8, 0x9A, 0xA9, 0x9B, 0xB9,
                        0xAB, 0xBA, 0x00, 0x11, 0x22, 0x33, 0x44, 0x55,
                        0x88, 0x99, 0xAA, 0xBB
                    ]:
                raise ValueError(
                    "[{}] of [{}] to [{}] not allowed".format(self.instruction.mnemonic, registers[0], registers[1]))

        code_pkg.post_byte = NumericValue(code_pkg.post_byte)
        return code_pkg


class RelativeOperand(Operand):
    def __init__(self, operand_string, instruction, value=None):
        super().__init__(instruction)
        self.type = OperandType.RELATIVE
        if not instruction.is_short_branch and not instruction.is_long_branch:
            raise ValueError("[{}] is not a branch instruction".format(instruction.mnemonic))
        self.operand_string = operand_string
        self.value = value if value else Value.create_from_str(operand_string, instruction)

    def translate(self):
        code_pkg = CodePackage()
        code_pkg.op_code = NumericValue(self.instruction.mode.rel)
        if self.value.is_type(ValueType.ADDRESS):
            code_pkg.additional = self.value
        code_pkg.size = self.instruction.mode.rel_sz
        return code_pkg


class InherentOperand(Operand):
    def __init__(self, operand_string, instruction, value=None):
        super().__init__(instruction)
        self.type = OperandType.INHERENT
        if value:
            raise ValueError("[{}] is not an inherent value".format(value.ascii()))
        if operand_string:
            raise ValueError("[{}] is not an inherent value".format(operand_string))

    def translate(self):
        if not self.instruction.mode.inh:
            raise ValueError("Instruction [{}] requires an operand".format(self.instruction.mnemonic))
        return CodePackage(op_code=NumericValue(self.instruction.mode.inh), size=self.instruction.mode.inh_sz)


class ImmediateOperand(Operand):
    def __init__(self, operand_string, instruction, value=None):
        super().__init__(instruction)
        self.type = OperandType.IMMEDIATE
        self.operand_string = operand_string
        if value:
            self.value = value
            return
        match = IMMEDIATE_REGEX.match(operand_string)
        if not match:
            raise ValueError("[{}] is not an immediate value".format(operand_string))
        self.value = Value.create_from_str(match.group("value"), instruction)

    def resolve_symbols(self, symbol_table):
        if not self.value.is_type(ValueType.SYMBOL):
            return self

        symbol = self.get_symbol(self.value.ascii(), symbol_table)
        self.value = copy(symbol)

        return self

    def translate(self):
        if not self.instruction.mode.imm:
            raise ValueError("Instruction [{}] does not support immediate addressing".format(self.instruction.mnemonic))
        return CodePackage(op_code=NumericValue(self.instruction.mode.imm),
                           additional=self.value,
                           size=self.instruction.mode.imm_sz)


class DirectOperand(Operand):
    def __init__(self, operand_string, instruction, value=None):
        super().__init__(instruction)
        self.type = OperandType.DIRECT
        self.operand_string = operand_string
        if value:
            self.value = value
            return
        match = DIRECT_REGEX.match(self.operand_string)
        if match:
            self.value = Value.create_from_str(match.group("value"), instruction)
        else:
            self.value = Value.create_from_str(operand_string, instruction)
        if self.value is None or self.value.byte_len() != 1:
            raise ValueError("[{}] is not a direct value".format(operand_string))

    def translate(self):
        if not self.instruction.mode.dir:
            raise ValueError("Instruction [{}] does not support direct addressing".format(self.instruction.mnemonic))
        return CodePackage(op_code=NumericValue(self.instruction.mode.dir),
                           additional=self.value,
                           size=self.instruction.mode.dir_sz)


class ExtendedOperand(Operand):
    def __init__(self, operand_string, instruction, value=None):
        super().__init__(instruction)
        self.type = OperandType.EXTENDED
        self.operand_string = operand_string
        if value:
            self.value = value
            return
        match = EXTENDED_REGEX.match(self.operand_string)
        if match:
            self.value = Value.create_from_str(match.group("value"), instruction)
        else:
            self.value = Value.create_from_str(operand_string, instruction)

        if self.value is None or self.value.byte_len() != 2:
            raise ValueError("[{}] is not an extended value".format(operand_string))

    def translate(self):
        if not self.instruction.mode.ext:
            raise ValueError("Instruction [{}] does not support extended addressing".format(self.instruction.mnemonic))
        return CodePackage(op_code=NumericValue(self.instruction.mode.ext),
                           additional=self.value,
                           size=self.instruction.mode.ext_sz)


class ExtendedIndexedOperand(Operand):
    def __init__(self, operand_string, instruction, value=None):
        super().__init__(instruction)
        self.type = OperandType.EXTENDED_INDIRECT
        self.operand_string = operand_string
        self.left = None
        self.right = None
        if value is not None:
            self.value = value
            return
        match = EXTENDED_INDIRECT_REGEX.match(self.operand_string)
        if not match:
            raise ValueError("[{}] is not an extended indexed value".format(operand_string))
        parsed_value = match.group("value")
        if "," not in parsed_value:
            self.value = Value.create_from_str(parsed_value, self.instruction)
        elif len(parsed_value.split(",")) == 2:
            self.left, self.right = parsed_value.split(",")
        else:
            raise ValueError("[{}] incorrect number of commas in extended indexed value".format(operand_string))

    def resolve_symbols(self, symbol_table):
        if not self.value.is_type(ValueType.NONE) and self.value.is_type(ValueType.SYMBOL):
            self.value = self.get_symbol(self.value.ascii(), symbol_table)
            return self

        if self.left and self.left != "":
            if self.left != "A" and self.left != "B" and self.left != "D":
                self.left = Value.create_from_str(self.left, self.instruction)
                if self.left.is_type(ValueType.SYMBOL):
                    self.left = self.get_symbol(self.left.ascii(), symbol_table)
        return self

    def translate(self):
        if not self.instruction.mode.ind:
            raise ValueError("Instruction [{}] does not support indexed addressing".format(self.instruction.mnemonic))
        size = self.instruction.mode.ind_sz

        if not type(self.value) == str and self.value.is_type(ValueType.ADDRESS):
            size += 2
            return CodePackage(
                op_code=NumericValue(self.instruction.mode.ind),
                post_byte=NumericValue(0x9F),
                additional=self.value,
                size=size)

        if not type(self.value) == str and self.value.is_type(ValueType.NUMERIC):
            size += 2
            return CodePackage(
                op_code=NumericValue(self.instruction.mode.ind),
                post_byte=NumericValue(0x9F),
                additional=self.value,
                size=size)

        raw_post_byte = 0x80
        additional = NoneValue()

        if "X" in self.right:
            raw_post_byte |= 0x00
        if "Y" in self.right:
            raw_post_byte |= 0x20
        if "U" in self.right:
            raw_post_byte |= 0x40
        if "S" in self.right:
            raw_post_byte |= 0x60

        if self.left == "":
            if "-" in self.right or "+" in self.right:
                if self.right == "X+" or self.right == "Y+" or self.right == "U+" or self.right == "S+":
                    raise ValueError("[{}] not allowed as an extended indirect value".format(self.right))
                if self.right == "-X" or self.right == "-Y" or self.right == "-U" or self.right == "-S":
                    raise ValueError("[{}] not allowed as an extended indirect value".format(self.right))
                if "++" in self.right:
                    raw_post_byte |= 0x11
                if "--" in self.right:
                    raw_post_byte |= 0x13
            else:
                raw_post_byte |= 0x14

        elif self.left == "A" or self.left == "B" or self.left == "D":
            if self.left == "A":
                raw_post_byte |= 0x16
            if self.left == "B":
                raw_post_byte |= 0x15
            if self.left == "D":
                raw_post_byte |= 0x1B

        else:
            if "+" in self.right or "-" in self.right:
                raise ValueError("[{}] invalid indexed expression".format(self.operand_string))
            if type(self.left) == str:
                self.left = NumericValue(self.left)
            if self.left.is_type(ValueType.ADDRESS):
                raise ValueError("[{}] cannot translate address in left hand side".format(self.operand_string))
            numeric = self.left
            if numeric.byte_len() == 2:
                size += 2
                if "PC" in self.right:
                    raw_post_byte |= 0x9D
                    additional = numeric
                else:
                    raw_post_byte |= 0x99
                    additional = numeric
            elif numeric.byte_len() == 1:
                size += 1
                if "PC" in self.right:
                    raw_post_byte |= 0x9C
                    additional = numeric
                else:
                    raw_post_byte |= 0x98
                    additional = numeric

        return CodePackage(op_code=NumericValue(self.instruction.mode.ind),
                           post_byte=NumericValue(raw_post_byte),
                           additional=additional,
                           size=size)


class IndexedOperand(Operand):
    def __init__(self, operand_string, instruction):
        super().__init__(instruction)
        self.type = OperandType.INDEXED
        self.operand_string = operand_string
        self.right = ""
        self.left = ""
        if "," not in operand_string or instruction.is_string_define:
            raise ValueError("[{}] is not an indexed value".format(operand_string))
        if len(operand_string.split(",")) != 2:
            raise ValueError("[{}] incorrect number of commas in indexed value".format(operand_string))
        self.left, self.right = operand_string.split(",")

    def resolve_symbols(self, symbol_table):
        if self.left != "":
            if self.left != "A" and self.left != "B" and self.left != "D":
                self.left = Value.create_from_str(self.left, self.instruction)
                if self.left.is_type(ValueType.SYMBOL):
                    self.left = self.get_symbol(self.left.ascii(), symbol_table)
        return self

    def translate(self):
        if not self.instruction.mode.ind:
            raise ValueError("Instruction [{}] does not support indexed addressing".format(self.instruction.mnemonic))
        raw_post_byte = 0x00
        size = self.instruction.mode.ind_sz
        additional = NoneValue()

        # Determine register (if any)
        if "X" in self.right:
            raw_post_byte |= 0x00
        if "Y" in self.right:
            raw_post_byte |= 0x20
        if "U" in self.right:
            raw_post_byte |= 0x40
        if "S" in self.right:
            raw_post_byte |= 0x60

        if self.left == "":
            raw_post_byte |= 0x80
            if "-" in self.right or "+" in self.right:
                if "+" in self.right:
                    raw_post_byte |= 0x00
                if "++" in self.right:
                    raw_post_byte |= 0x01
                if "-" in self.right:
                    raw_post_byte |= 0x02
                if "--" in self.right:
                    raw_post_byte |= 0x03
            else:
                raw_post_byte |= 0x04

        elif self.left == "A" or self.left == "B" or self.left == "D":
            raw_post_byte |= 0x80
            if self.left == "A":
                raw_post_byte |= 0x06
            if self.left == "B":
                raw_post_byte |= 0x05
            if self.left == "D":
                raw_post_byte |= 0x0B

        else:
            if "+" in self.right or "-" in self.right:
                raise ValueError("[{}] invalid indexed expression".format(self.operand_string))
            if type(self.left) == str:
                self.left = NumericValue(self.left)
            if self.left.is_type(ValueType.ADDRESS):
                raise ValueError("[{}] cannot translate address in left hand side".format(self.operand_string))
            numeric = self.left
            if numeric.byte_len() == 2:
                size += 2
                if "PC" in self.right:
                    raw_post_byte |= 0x8D
                    additional = numeric
                else:
                    raw_post_byte |= 0x89
                    additional = numeric
            elif numeric.byte_len() == 1:
                if "PC" in self.right:
                    raw_post_byte |= 0x8C
                    additional = numeric
                    size += 1
                else:
                    if numeric.int <= 0x1F:
                        raw_post_byte |= numeric.int
                    else:
                        raw_post_byte |= 0x88
                        additional = numeric
                        size += 1

        return CodePackage(op_code=NumericValue(self.instruction.mode.ind),
                           post_byte=NumericValue(raw_post_byte),
                           additional=additional,
                           size=size)


class ExpressionOperand(Operand):
    def __init__(self, operand_string, instruction, value=None):
        super().__init__(instruction)
        self.type = OperandType.EXPRESSION
        self.operand_string = operand_string
        match = EXPRESSION_REGEX.match(operand_string)
        if not match:
            raise ValueError("[{}] is not a valid expression".format(operand_string))
        self.left = Value.create_from_str(match.group("left"), instruction)
        self.right = Value.create_from_str(match.group("right"), instruction)
        self.operation = match.group("operation")
        self.value = NoneValue("")

    def translate(self):
        return CodePackage()

# E N D   O F   F I L E #######################################################
