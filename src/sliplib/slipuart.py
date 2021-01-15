#  Copyright (c) 2020. Ruud de Jong
#  This file is part of the SlipLib project which is released under the MIT license.
#  See https://github.com/rhjdjong/SlipLib for details.

"""
SlipUart
----------

.. autoclass:: SlipUart(stream, [chunk_size])
   :show-inheritance:

   A :class:`SlipUart` instance has the following attributes in addition to the attributes
   offered by its base class :class:`SlipWrapper`:

   .. autoattribute:: readable
   .. autoattribute:: writable
"""

import serial
import warnings
from typing import Any
try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol  # type: ignore
from .slipwrapper import SlipWrapper

class SlipUart(SlipWrapper):
    """Class that wraps an UART stream with a :class:`Driver`

    :class:`SlipUart` combines a :class:`Driver` instance with a UART.

    The :class:`SlipUart` class has all the methods and attributes
    from its base class :class:`SlipWrapper`.
    In addition it directly exposes all methods and attributes of
    the contained :obj:`stream`, except for the following:

     * :meth:`read*` and :meth:`write*`. These methods are not
       supported, because byte-oriented read and write operations
       would invalidate the internal state maintained by :class:`SlipUart`.
     * Similarly, :meth:`seek`, :meth:`tell`, and :meth:`truncate` are not supported,
       because repositioning or truncating the stream would invalidate the internal state.
     * :meth:`raw`, :meth:`detach` and other methods that provide access to or manipulate
       the stream's internal data.

    In stead of the :meth:`read*` and :meth:`write*` methods
    a :class:`SlipUart` object provides the method :meth:`recv_msg` and :meth:`send_msg`
    to read and write SLIP-encoded messages.

    .. deprecated:: 0.6
       Direct access to the methods and attributes of the contained :obj:`stream`
       will be removed in version 1.0

    """
    def __init__(self, uart: serial.Serial, chunk_size: int = 1):
        # pylint: disable=missing-raises-doc
        """
        To instantiate a :class:`SlipUart` object, the user must provide
        a pre-constructed open byte stream that is ready for reading and/or writing

        Args:
            uart (bytestream): The byte stream that will be wrapped.

            chunk_size: the number of bytes to read per read operation.
                The default value for `chunck_size` is 1.
                Setting the `chunk_size` is useful when the stream has a low bandwidth
                and/or bursty data (e.g. a serial port interface).
                In such cases it is useful to have a `chunk_size` of 1, to avoid that the application
                hangs or becomes unresponsive.

        .. versionadded:: 0.6
           The `chunk_size` parameter.

        A :class:`SlipUart` instance can e.g. be useful to read slip-encoded messages
        from a file:

        .. code::

            with open('/path/to/a/slip/encoded/file', mode='rb') as f:
                slip_file = SlipUart(f)
                for msg in slip_file:
                    # Do something with the message

        """
        self._chunk_size = chunk_size if chunk_size > 0 else 1
        self._uart = uart
        super().__init__(self._uart)

    def send_bytes(self, packet: bytes) -> None:
        """See base class"""
        print('SlipUart.send_bytes: {}'.format(packet.hex()))
        while packet:
            number_of_bytes_written = self.stream.write(packet)
            packet = packet[number_of_bytes_written:]

    def recv_bytes(self) -> bytes:
        """See base class"""
        ret = b'' if self._stream_is_closed else self.stream.read(self._chunk_size)
        # if ret:
        #     print('SlipUart.recv_bytes: {}'.format(ret.hex()))
        return ret

    def read_timed_out(self) -> bool:
        """See base class"""
        # Always assume timeout triggered if asked
        return self._uart.timeout is not None

    @property
    def readable(self) -> bool:
        """Indicates if the wrapped stream is readable.
        The value is `True` if the readability of the wrapped stream
        cannot be determined.
        """
        return getattr(self.stream, 'readable', True)

    @property
    def writable(self) -> bool:
        """Indicates if the wrapped stream is writable.
        The value is `True` if the writabilty of the wrapped stream
        cannot be determined.
        """
        return getattr(self.stream, 'writable', True)

    @property
    def _stream_is_closed(self) -> bool:
        """Indicates if the UART is closed.
        """
        return not self._uart.is_open

    def __getattr__(self, attribute: str) -> Any:
        if attribute.startswith('read') or attribute.startswith('write') or attribute in (
                'detach', 'flushInput', 'flushOutput', 'getbuffer', 'getvalue', 'peek', 'raw', 'reset_input_buffer',
                'reset_output_buffer', 'seek', 'seekable', 'tell', 'truncate'
        ):
            raise AttributeError("'{}' object has no attribute '{}'".
                                 format(self.__class__.__name__, attribute))
        warnings.warn("Direct access to the enclosed stream attributes and methods will be removed in version 1.0",
                      DeprecationWarning, stacklevel=2)
        return getattr(self.stream, attribute)
