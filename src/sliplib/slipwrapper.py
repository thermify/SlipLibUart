#  Copyright (c) 2020. Ruud de Jong
#  This file is part of the SlipLib project which is released under the MIT license.
#  See https://github.com/rhjdjong/SlipLib for details.

"""
SlipWrapper
-----------

.. autoclass:: SlipWrapper

   Class :class:`SlipWrapper` offers the following methods and attributes:

   .. automethod:: send_msg
   .. automethod:: recv_msg

   .. attribute:: driver

      The :class:`SlipWrapper`'s :class:`Driver` instance.

   .. attribute:: stream

      The wrapped `stream`.

   In addition, :class:`SlipWrapper` requires that derived classes implement the following methods:

   .. automethod:: send_bytes
   .. automethod:: recv_bytes
"""

import logging

logger = logging.getLogger(__name__)

import collections
import sys
from typing import Any

from .slip import Driver, ProtocolError


class SlipWrapper:
    """Base class that provides a message based interface to a byte stream

    :class:`SlipWrapper` combines a :class:`Driver` instance with a byte stream.
    The :class:`SlipWrapper` class is an abstract base class.
    It offers the methods :meth:`send_msg` and :meth:`recv_msg` to send and
    receive single messages over the byte stream, but it does not of itself
    provide the means to interact with the stream.

    To interact with a concrete stream, a derived class must implement
    the methods :meth:`send_bytes` and :meth:`recv_bytes`
    to write to and read from the stream.

    A :class:`SlipWrapper` instance can be iterated over.
    Each iteration will provide the next message that is received from the byte stream.

    .. versionchanged:: 0.5
       Allow iteration over a :class:`SlipWrapper` instance.
    """

    def __init__(self, stream: Any):
        """
        To instantiate a :class:`SlipWrapper`, the user must provide
        an existing byte stream

        Args:
            stream (bytestream): The byte stream that will be wrapped.
        """
        self.stream = stream
        self.driver = Driver()
        self._messages = collections.deque()  # type: Deque[bytes]
        self._protocol_error = None  # type: Optional[ProtocolError]
        self._traceback = None  # type: Optional[TracebackType]
        self._flush_needed = False
        self._stream_closed = False

    def send_bytes(self, packet: bytes) -> None:
        """Send a packet over the stream.

        Derived classes must implement this method.

        Args:
            packet: the packet to send over the stream
        """
        raise NotImplementedError

    def recv_bytes(self) -> bytes:
        """Receive data from the stream.

        Derived classes must implement this method.

        .. note::
            The convention used within the :class:`SlipWrapper` class
            is that :meth:`recv_bytes` returns an empty bytes object
            to indicate that the end of
            the byte stream has been reached and no further data will
            be received. Derived implementations must ensure that
            this convention is followed.

        Returns:
            The bytes received from the stream
        """
        raise NotImplementedError

    def read_timed_out(self) -> bool:
        """Check if stream timed out on read"""
        raise NotImplementedError

    def send_msg(self, message: bytes) -> None:
        """Send a SLIP-encoded message over the stream.

        Args:
            message (bytes): The message to encode and send
        """
        packet = self.driver.send(message)
        self.send_bytes(packet)

    def recv_msg(self) -> bytes:
        """Receive a single message from the stream.

        Returns:
            bytes:  A SLIP-decoded message

        Raises:
            ProtocolError: when a SLIP protocol error has been encountered.
                A subsequent call to :meth:`recv_msg` (after handling the exception)
                will return the message from the next packet.
        """

        # First check if there are any pending messages
        if self._messages:
            return self._messages.popleft()

        # No pending messages left. If a ProtocolError has occurred
        # it must be re-raised here:
        self._handle_pending_protocol_error()

        while not self._messages and not self._stream_closed:
            # As long as no messages are available,
            # flush the internal packet buffer,
            # and try to read data
            try:
                if self._flush_needed:
                    self._flush_needed = False
                    self._messages.extend(self.driver.flush())
                else:
                    data = self.recv_bytes()
                    # if data != b'':
                    #     logger.debug('SlipWrapper.recv_msg: {}'.format(data))
                    if data == b"":
                        if self.read_timed_out():
                            logger.debug("SlipWrapper.recv_msg: read timed out")
                        else:
                            logger.error(
                                "SlipWrapper.recv_msg: read error, closing stream"
                            )
                            self._stream_closed = True
                        break
                    if isinstance(
                        data, int
                    ):  # Single byte reads are represented as integers
                        data = bytes([data])
                    self._messages.extend(self.driver.receive(data))
            except ProtocolError as protocol_error:
                self._messages.extend(self.driver.messages)
                self._protocol_error = protocol_error
                self._traceback = sys.exc_info()[2]
                break

        if self._messages:
            return self._messages.popleft()

        self._handle_pending_protocol_error()
        return b""

    def _handle_pending_protocol_error(self) -> None:
        if self._protocol_error:
            try:
                raise self._protocol_error.with_traceback(self._traceback)
            finally:
                self._protocol_error = None
                self._traceback = None
                self._flush_needed = True

    def __iter__(self):
        while True:
            msg = self.recv_msg()
            if not msg:
                break
            yield msg
