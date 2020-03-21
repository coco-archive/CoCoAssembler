"""
Copyright (C) 2019-2020 Craig Thomas

This project uses an MIT style license - see LICENSE for details.
A Color Computer Assembler - see the README.md file for details.
"""
# I M P O R T S ###############################################################

import re

from copy import copy

from cocoasm.exceptions import ParseError, TranslationError
from cocoasm.instruction import INSTRUCTIONS, InstructionBundle
from cocoasm.operands import Operand, OperandType
from cocoasm.values import ValueType
from cocoasm.helpers import hex_value

# C O N S T A N T S ###########################################################

# Pattern to recognize a blank line
BLANK_LINE_REGEX = re.compile(r"^\s*$")

# Pattern to parse a comment line
COMMENT_LINE_REGEX = re.compile(r"^\s*;\s*(?P<comment>.*)$")

# Pattern to parse a single line
ASM_LINE_REGEX = re.compile(
    r"^(?P<label>[\w@]*)\s+(?P<mnemonic>\w*)\s+(?P<operands>[\w\[\]#$,+-.*@\"]*)\s*[;]*(?P<comment>.*)$"
)

# Pattern to recognize a direct value
DIR_REGEX = re.compile(
    r"^<(?P<value>.*)"
)

# C L A S S E S  ##############################################################


class Statement(object):
    """
    The Statement class represents a single line of assembly language. Each
    statement is constructed from a single line that has the following format:

        LABEL   MNEMONIC   OPERANDS    COMMENT

    The statement can be parsed and translated to its Chip8 machine code
    equivalent.
    """
    def __init__(self, line):
        self.is_empty = True
        self.is_comment_only = False
        self.instruction = None
        self.label = None
        self.operand = None
        self.original_operand = None
        self.comment = None
        self.size = 0
        self.mnemonic = None
        self.state = None
        self.instruction_bundle = InstructionBundle()
        self.parse_line(line)

    def __str__(self):
        op_code_string = ""
        if self.get_op_codes():
            op_code_string += self.get_op_codes()
        if self.get_post_byte():
            op_code_string += self.get_post_byte()
        if self.get_additional():
            op_code_string += self.get_additional()

        return "${} {:.10} {} {} {} ; {} {} {}".format(
            self.get_address(),
            op_code_string.ljust(10, ' '),
            self.get_label().rjust(10, ' '),
            self.get_mnemonic().rjust(5, ' '),
            self.original_operand.operand_string.ljust(30, ' '),
            self.get_comment().ljust(40, ' '),
            self.operand.type,
            self.operand.value.type
        )

    def get_address(self):
        """
        Returns the address for this statement.

        :return: the address for this statement
        """
        if self.instruction_bundle:
            return hex_value(self.instruction_bundle.address, 4)
        return "None"

    def get_label(self):
        """
        Returns the label associated with this statement.

        :return: the label for this statement
        """
        return self.label or ""

    def get_mnemonic(self):
        """
        Returns the mnemonic for this statement.

        :return: the mnemonic for this statement
        """
        return self.mnemonic or ""

    def get_op_codes(self):
        """
        Returns the operation codes for this statement.

        :return: the operation codes for this statement
        """
        if self.instruction_bundle:
            return hex_value(self.instruction_bundle.op_code) or None
        return None

    def get_additional(self):
        if self.instruction_bundle:
            return self.instruction_bundle.additional or None
        return None

    def get_post_byte(self):
        if self.instruction_bundle:
            return hex_value(self.instruction_bundle.post_byte) or None
        return None

    def get_comment(self):
        """
        Returns the comment for this statement.

        :return: the comment for this statement
        """
        return self.comment if self.comment else ""

    def match_operation(self):
        """
        Returns the instruction with the specified mnemonic, or None if the
        mnemonic does not exist.

        :return: the instruction associated with the mnemonic
        """
        return next((op for op in INSTRUCTIONS if op.mnemonic == self.mnemonic), None)

    def get_include_filename(self):
        """
        Returns the name of the file to include in the current stream of
        statements if the statement is the pseudo op INCLUDE, and there is
        a value for the operand

        :return: the name of the file to include
        """
        return self.operand.get_operand_string() if self.instruction.is_include() else None

    def parse_line(self, line):
        """
        Parse a line of assembly language text.

        :param line: the line of text to parse
        """
        if BLANK_LINE_REGEX.search(line):
            return

        data = COMMENT_LINE_REGEX.match(line)
        if data:
            self.is_empty = False
            self.is_comment_only = True
            self.comment = data.group("comment").strip()
            return

        data = ASM_LINE_REGEX.match(line)
        if data:
            self.label = data.group("label") or None
            self.mnemonic = data.group("mnemonic").upper() or None
            if self.mnemonic == "FCC":
                original_operand = data.group("operands")
                if data.group("comment"):
                    original_operand = "{} {}".format(data.group("operands"), data.group("comment").strip())
                starting_symbol = original_operand[0]
                ending_location = original_operand.find(starting_symbol, 1)
                self.operand = Operand.create_from_str(original_operand[0:ending_location + 1], self.mnemonic)
                self.original_operand = copy(self.operand)
                self.comment = original_operand[ending_location + 2:].strip() or None
                self.is_empty = False
            else:
                self.operand = Operand.create_from_str(data.group("operands"), self.mnemonic)
                self.original_operand = copy(self.operand)
                self.comment = data.group("comment").strip() or None
                self.is_empty = False
            return

        raise ParseError("Could not parse line [{}]".format(line), self)

    def match_mnemonic(self):
        self.instruction = copy(self.match_operation())
        if not self.instruction:
            raise TranslationError("Invalid mnemonic [{}]".format(self.mnemonic), self)

    def set_address(self, address):
        if self.instruction_bundle.address is not None:
            return int(self.instruction_bundle.address, 16)
        self.instruction_bundle.address = address
        return self.instruction_bundle.address

    def translate_pseudo(self, symbol_table):
        if self.instruction.is_pseudo():
            self.instruction_bundle = self.instruction.translate_pseudo(self.get_label(), self.operand, symbol_table)
            if self.instruction_bundle:
                self.size = self.instruction_bundle.get_size()

    def translate(self, symbol_table):
        """
        Translate the mnemonic into an actual operation.

        :param symbol_table: the dictionary of symbol table elements
        """
        if self.instruction.is_pseudo():
            return

        if self.instruction.is_special():
            self.instruction_bundle = self.instruction.translate_special(self.operand, self)
            self.size = self.instruction_bundle.get_size()
            return

        self.operand.resolve_symbols(symbol_table)

        if self.instruction.is_short_branch or self.instruction.is_long_branch:
            self.instruction_bundle.op_code = self.instruction.mode.rel
            if self.operand.value.is_type(ValueType.ADDRESS):
                self.instruction_bundle.additional = self.operand.value.hex()
            self.size = self.instruction.mode.rel_sz
            return

        if self.operand.is_type(OperandType.INHERENT):
            if not self.instruction.mode.supports_inherent():
                raise TranslationError("Instruction [{}] requires an operand".format(self.mnemonic), self)
            self.instruction_bundle.op_code = self.instruction.mode.inh
            self.size = self.instruction.mode.inh_sz

        if self.operand.is_type(OperandType.IMMEDIATE):
            if not self.instruction.mode.supports_immediate():
                raise TranslationError("Instruction [{}] does not support immediate addressing".format(self.mnemonic),
                                       self)
            self.instruction_bundle.op_code = self.instruction.mode.imm
            self.instruction_bundle.additional = self.operand.value.hex()
            self.size = self.instruction.mode.imm_sz

        if self.operand.is_type(OperandType.INDEXED):
            if not self.instruction.mode.supports_indexed():
                raise TranslationError("Instruction [{}] does not support indexed addressing".format(self.mnemonic),
                                       self)
            self.instruction_bundle.op_code = self.instruction.mode.ind
            self.instruction_bundle.additional = self.operand.value.hex()
            # TODO: properly translate what the post-byte code should be
            self.instruction_bundle.post_byte = 0x9F
            self.size = self.instruction.mode.ind_sz

        if self.operand.is_type(OperandType.DIRECT):
            if not self.instruction.mode.supports_direct():
                raise TranslationError("Instruction [{}] does not support direct addressing".format(self.mnemonic),
                                       self)
            self.instruction_bundle.op_code = self.instruction.mode.dir
            self.instruction_bundle.additional = self.operand.value.hex()
            self.size = self.instruction.mode.dir_sz

        if self.operand.is_type(OperandType.EXTENDED):
            if not self.instruction.mode.supports_extended():
                raise TranslationError("Instruction [{}] does not support extended addressing".format(self.mnemonic),
                                       self)
            self.instruction_bundle.op_code = self.instruction.mode.ext
            self.instruction_bundle.additional = self.operand.value.hex()
            self.size = self.instruction.mode.ext_sz

    def fix_addresses(self, statements, this_index):
        if self.instruction.is_short_branch:
            branch_index = int(self.instruction_bundle.additional, 16)
            length = 0
            if branch_index < this_index:
                length = 1
                for statement in statements[branch_index:this_index]:
                    length += statement.size
                self.instruction_bundle.additional = "{:02X}".format(0xFF - length)
            else:
                for statement in statements[this_index+1:branch_index]:
                    length += statement.size
                self.instruction_bundle.additional = "{:02X}".format(length)
            return

        if self.instruction.is_long_branch:
            branch_index = int(self.instruction_bundle.additional, 16)
            length = 0
            if branch_index < this_index:
                length = 1
                for statement in statements[branch_index:this_index]:
                    length += statement.size
                self.instruction_bundle.additional = "{:04X}".format(0xFFFF - length)
            else:
                for statement in statements[this_index+1:branch_index]:
                    length += statement.size
                self.instruction_bundle.additional = "{:04X}".format(length)
            return

        if self.operand.value.is_type(ValueType.ADDRESS):
            self.instruction_bundle.additional = statements[int(self.operand.value.hex(), 16)].get_address()

# E N D   O F   F I L E #######################################################
