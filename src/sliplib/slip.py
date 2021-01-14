#  Copyright (c) 2020. Ruud de Jong
#  This file is part of the SlipLib project which is released under the MIT license.
#  See https://github.com/rhjdjong/SlipLib for details.

"""
Constants
---------

.. data:: END
.. data:: ESC
.. data:: ESC_END
.. data:: ESC_ESC

   These constants represent the special bytes
   used by SLIP for delimiting and encoding messages.

Functions
---------

The following are lower-level functions, that should normally not be used directly.

.. autofunction:: encode
.. autofunction:: decode
.. autofunction:: is_valid

Classes
-------

.. autoclass:: Driver

   Class :class:`Driver` offers the following methods:

   .. automethod:: send
   .. automethod:: receive

   To enable recovery from a :exc:`ProtocolError`, the
   :class:`Driver` class offers the following attribute and method:

   .. autoattribute:: messages
   .. automethod:: flush
"""

import collections
import re
from typing import Deque, List, Union
from datetime import datetime, timedelta

END = b'\xc0'
ESC = b'\xdb'
ESC_END = b'\xdc'
ESC_ESC = b'\xdd'

"""These constants represent the special SLIP bytes"""

# When receceiving a SLIP frame start, it must complete reception in this time
# (regardless of its length, sorry) to avoid corrupt/missing END byte from
# flipping the frame reception state machine out of phase with sender.
SLIP_FRAME_COMPLETION_TIMEOUT_S = 3

class ProtocolError(ValueError):
    """Exception to indicate that a SLIP protocol error has occurred.

    This exception is raised when an attempt is made to decode
    a packet with an invalid byte sequence.
    An invalid byte sequence is either an :const:`ESC` byte followed
    by any byte that is not an :const:`ESC_ESC` or :const:`ESC_END` byte,
    or a trailing :const:`ESC` byte as last byte of the packet.

    The :exc:`ProtocolError` carries the invalid packet
    as the first (and only) element in in its :attr:`args` tuple.
    """


def encode(msg: bytes) -> bytes:
    """Encodes a message (a byte sequence) into a SLIP-encoded packet.

    Args:
        msg: The message that must be encoded

    Returns:
        The SLIP-encoded message
    """
    msg = bytes(msg)
    return END + msg.replace(ESC, ESC + ESC_ESC).replace(END, ESC + ESC_END) + END


def decode(packet: bytes) -> bytes:
    """Retrieves the message from the SLIP-encoded packet.

    Args:
        packet: The SLIP-encoded message.
           Note that this must be exactly one complete packet.
           The :func:`decode` function does not provide any buffering
           for incomplete packages, nor does it provide support
           for decoding data with multiple packets.
    Returns:
        The decoded message

    Raises:
        ProtocolError: if the packet contains an invalid byte sequence.
    """
    if not is_valid(packet):
        raise ProtocolError(packet)
    return packet.strip(END).replace(ESC + ESC_END, END).replace(ESC + ESC_ESC, ESC)


def is_valid(packet: bytes) -> bool:
    """Indicates if the packet's contents conform to the SLIP specification.

    A packet is valid if:

    * It contains no :const:`END` bytes other than leading and/or trailing :const:`END` bytes, and
    * Each :const:`ESC` byte is followed by either an :const:`ESC_END` or an :const:`ESC_ESC` byte.

    Args:
        packet: The packet to inspect.

    Returns:
        :const:`True` if the packet is valid, :const:`False` otherwise
    """

    valid = not (END in packet or
                packet.endswith(ESC) or
                re.search(ESC + b'[^' + ESC_END + ESC_ESC + b']', packet))
    print('is_valid: {} {}'.format(packet.hex(), valid))
    return valid


class Driver:
    """Class to handle the SLIP-encoding and decoding of messages

    This class manages the handling of encoding and decoding of
    messages according to the SLIP protocol.
    """

    def __init__(self) -> None:
        self._recv_buffer = bytearray()
        self._packets = collections.deque()  # type: Deque[bytes]
        self._messages = []  # type: List[bytes]
        self._curr_frame = None # indicates whe're in the middle of receiving a frame
        self._curr_frame_deadline = None # Timeout for completing a frame

    def send(self, message: bytes) -> bytes:  # pylint: disable=no-self-use
        """Encodes a message into a SLIP-encoded packet.

        The message can be any arbitrary byte sequence.

        Args:
            message: The message that must be encoded.

        Returns:
            A packet with the SLIP-encoded message.
        """
        return encode(message)

    def receive(self, data: Union[bytes, int]) -> List[bytes]:
        """Decodes data and gives a list of decoded messages.

        Processes :obj:`data`, which must be a bytes-like object,
        and returns a (possibly empty) list with :class:`bytes` objects,
        each containing a decoded message.
        Any non-terminated SLIP packets in :obj:`data`
        are buffered, and processed with the next call to :meth:`receive`.

        Args:
            data: A bytes-like object to be processed.

                An empty :obj:`data` parameter forces the internal
                buffer to be flushed and decoded.

                To accommodate iteration over byte sequences, an
                integer in the range(0, 256) is also accepted.

        Returns:
            A (possibly empty) list of decoded messages.

        Raises:
            ProtocolError: When `data` contains an invalid byte sequence.
        """

        if data != b'':
            # When a single byte is fed into this function
            # it is received as an integer, not as a bytes object.
            # It must first be converted into a bytes object.
            if isinstance(data, int):
                print('Driver.receive: making bytes from int {}'.format(hex(data)))
                data = bytes((data,))

            self._recv_buffer += data
            print('Driver.receive: got {} buffer now: {}'.format(data.hex(), self._recv_buffer.hex()))

            # The following situations can occur:
            #
            #  1) _recv_buffer is empty or contains only END bytes --> no packets available
            #  2) _recv_buffer contains non-END bytes -->  packets are available
            #  3) _recv_buffer contains out-of-frame garbage or frames with corrupt
            #   END bytes (which flips frame phase between sender and reciver)
            while len(self._recv_buffer) > 0:
                byte = bytes((self._recv_buffer.pop(0),))
                print('Driver.receive: pop from buffer {}'.format(byte.hex()))
                if byte == END:
                    if self._curr_frame is None:
                        # A frame has started
                        print('Driver.receive: got END, start frame')
                        self._curr_frame_deadline = datetime.now() + timedelta(seconds = SLIP_FRAME_COMPLETION_TIMEOUT_S)
                        self._curr_frame = bytearray(b'')
                    else:
                        # A frame has ended
                        if datetime.now() > self._curr_frame_deadline:
                            # Timeout for completing the current frame has expired.
                            # Assume END for current frame was lost or corrupted and
                            # this is the start of a subsequent frame. Declare current
                            # frame as lost and start new frame.
                            print('Driver.receive: frame timeout exceeded by {}'.format(datetime.now() - self._curr_frame_deadline))
                            self._curr_frame_deadline = datetime.now() + timedelta(seconds = SLIP_FRAME_COMPLETION_TIMEOUT_S)
                            self._curr_frame = bytearray(b'')
                        else:
                            print('Driver.receive: got END, end frame {}'.format(self._curr_frame.hex()))
                            self._packets.append(self._curr_frame)
                            self._curr_frame = None
                else:
                    if self._curr_frame is None:
                        print('Driver.receive: ignore out of frame garbage {}'.format(byte.hex()))
                    else:
                        self._curr_frame += byte

            if self._curr_frame is not None:
                # Not finished receivng the entire frame, restore the buffer
                # FIXME: copying the half-receivd frame back and forth
                self._recv_buffer = bytearray(END) + self._curr_frame
                self._curr_frame = None
                print('Driver.receive: restored RX buffer to {}'.format(self._recv_buffer.hex()))

        # Process the buffered packets
        return self.flush()

    def flush(self) -> List[bytes]:
        """Gives a list of decoded messages.

        Decodes the packets in the internal buffer.
        This enables the continuation of the processing
        of received packets after a :exc:`ProtocolError`
        has been handled.

        Returns:
            A (possibly empty) list of decoded messages from the buffered packets.

        Raises:
            ProtocolError: When any of the buffered packets contains an invalid byte sequence.
        """
        messages = []  # type: List[bytes]
        while self._packets:
            packet = self._packets.popleft()
            try:
                msg = decode(packet)
            except ProtocolError:
                # Add any already decoded messages to the exception
                self._messages = messages
                raise
            messages.append(msg)
        return messages

    @property
    def messages(self) -> List[bytes]:
        """A list of decoded messages.

        The read-only attribute :attr:`messages` contains
        the messages that were
        already decoded before a
        :exc:`ProtocolError` was raised.
        This enables the handler of the :exc:`ProtocolError`
        exception to recover the messages up to the
        point where the error occurred.
        This attribute is cleared after it has been read.
        """
        try:
            return self._messages
        finally:
            self._messages = []
