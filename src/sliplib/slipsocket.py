#  Copyright (c) 2020. Ruud de Jong
#  This file is part of the SlipLib project which is released under the MIT license.
#  See https://github.com/rhjdjong/SlipLib for details.

"""
SlipSocket
----------

.. autoclass:: SlipSocket(sock)
   :show-inheritance:

   Class :class:`SlipSocket` offers the following methods in addition to the methods
   offered by its base class :class:`SlipWrapper`:

   .. automethod:: accept
   .. automethod:: create_connection

   .. note::
       The :meth:`accept` and :meth:`create_connection` methods
       do not magically turn the
       socket at the remote address into a SlipSocket.
       For the connection to work properly,
       the remote socket must already
       have been configured to use the SLIP protocol.

   The following commonly used :class:`socket.socket` methods are exposed through
   a :class:`SlipSocket` object.
   These methods are simply delegated to the wrapped `socket` instance.

   .. automethod:: bind
   .. automethod:: close
   .. automethod:: connect
   .. automethod:: connect_ex
   .. automethod:: getpeername
   .. automethod:: getsockname
   .. automethod:: listen([backlog])
   .. automethod:: shutdown

   Since the wrapped socket is available as the :attr:`socket` attribute,
   any other :class:`socket.socket`
   method can be invoked through that attribute.

   .. warning::

      Avoid using :class:`socket.socket`
      methods that affect the bytes that are sent or received through the socket.
      Doing so will invalidate the internal state of the enclosed :class:`Driver` instance,
      resulting in corrupted SLIP messages.
      In particular, do not use any of the :meth:`recv*` or :meth:`send*` methods
      on the :attr:`socket` attribute.

   A :class:`SlipSocket` instance has the following attributes in addition to the attributes
   offered by its base class :class:`SlipWrapper`:

   .. attribute:: socket

      The wrapped `socket`.
      This is actually just an alias for the :attr:`stream` attribute in the base class.

   .. autoattribute:: family
   .. autoattribute:: type
   .. autoattribute:: proto
"""

import socket
import warnings
from typing import Optional, Tuple

from .slipwrapper import SlipWrapper


class SlipSocket(SlipWrapper):
    """Class that wraps a TCP :class:`socket` with a :class:`Driver`

    :class:`SlipSocket` combines a :class:`Driver` instance with a
    :class:`socket`.
    The :class:`SlipStream` class has all the methods from its base class :class:`SlipWrapper`.
    In addition it directly exposes all methods and attributes of
    the contained :obj:`socket`, except for the following:

    * :meth:`send*` and :meth:`recv*`. These methods are not
      supported, because byte-oriented send and receive operations
      would invalidate the internal state maintained by :class:`SlipSocket`.
    * Similarly, :meth:`makefile` is not supported, because byte- or line-oriented
      read and write operations would invalidate the internal state.
    * :meth:`share` (Windows only) and :meth:`dup`. The internal state of
      the :class:`SlipSocket` would have to be duplicated and shared to make these methods meaningful.
      Because of the lack of a convincing use case for this, sharing and duplication is
      not supported.
    * The :meth:`accept` method is delegated to the contained :class:`socket`,
      but the socket that is returned by the :class:`socket`'s :meth:`accept` method
      is automatically wrapped in a :class:`SlipSocket` object.

    In stead of the :class:`socket`'s :meth:`send*` and :meth:`recv*` methods
    a :class:`SlipSocket` provides the method :meth:`send_msg` and :meth:`recv_msg`
    to send and receive SLIP-encoded messages.

    .. deprecated:: 0.6
       Direct access to the methods and attributes of the contained :obj:`socket`
       other than `family`, `type`, and `proto` will be removed in version 1.0

    Only TCP sockets are supported. Using the SLIP protocol on
    UDP sockets is not supported for the following reasons:

    * UDP is datagram-based. Using SLIP with UDP therefore
      introduces ambiguity: should SLIP packets be allowed to span
      multiple UDP datagrams or not?
    * UDP does not guarantee delivery, and does not guarantee that
      datagrams are delivered in the correct order.

    """

    _chunk_size = 4096

    def __init__(self, sock: socket.SocketType):
        # pylint: disable=missing-raises-doc
        """
        To instantiate a :class:`SlipSocket`, the user must provide
        a pre-constructed TCP `socket`.
        An alternative way to instantiate s SlipSocket is to use the
        class method :meth:`create_connection`.

        Args:
            sock (socket.socket): An existing TCP socket, i.e.
                a socket with type :const:`socket.SOCK_STREAM`
        """

        if not isinstance(sock, socket.socket) or sock.type != socket.SOCK_STREAM:
            raise ValueError("Only sockets with type SOCK_STREAM are supported")
        super().__init__(sock)
        self.socket = self.stream

    def send_bytes(self, packet: bytes) -> None:
        """See base class"""
        self.socket.sendall(packet)

    def recv_bytes(self) -> bytes:
        """See base class"""
        return self.socket.recv(self._chunk_size)

    def accept(self) -> Tuple["SlipSocket", Tuple]:
        """Accepts an incoming connection.

        Returns:
            Tuple[:class:`~SlipSocket`, Tuple]: A (`SlipSocket`, remote_address) pair.
            The :class:`SlipSocket` object
            can be used to exchange SLIP-encoded data with the socket at the `remote_address`.

        See Also:
            :meth:`socket.socket.accept`
        """
        conn, address = self.socket.accept()
        return self.__class__(conn), address

    def bind(self, address: Tuple) -> None:
        """Bind the `SlipSocket` to `address`.

        Args:
            address: The IP address to bind to.

        See Also:
            :meth:`socket.socket.bind`
        """
        self.socket.bind(address)

    def close(self) -> None:
        """Close the `SlipSocket`.

        See Also:
            :meth:`socket.socket.close`
        """
        self.socket.close()

    def connect(self, address: Tuple) -> None:
        """Connect `SlipSocket` to a remote socket at `address`.

        Args:
            address: The IP address of the remote socket.

        See Also:
           :meth:`socket.socket.connect`
        """
        self.socket.connect(address)

    def connect_ex(self, address: Tuple) -> None:
        """Connect `SlipSocket` to a remote socket at `address`.

        Args:
            address: The IP address of the remote socket.

        See Also:
           :meth:`socket.socket.connect_ex`
        """
        self.socket.connect_ex(address)

    def getpeername(self) -> Tuple:
        """Get the IP address of the remote socket to which `SlipSocket` is connected.

        Returns:
            The remote IP address.

        See Also:
           :meth:`socket.socket.getpeername`
        """
        return self.socket.getpeername()

    def getsockname(self) -> Tuple:
        """Get `SlipSocket`'s own address.

        Returns:
            The local IP address.

        See Also:
           :meth:`socket.socket.getsockname`
        """
        return self.socket.getsockname()

    def listen(self, backlog: Optional[int] = None) -> None:
        """Enable a `SlipSocket` server to accept connections.

        Args:
            backlog (int): The maximum number of waiting connections.

        See Also:
            :meth:`socket.socket.listen`
        """
        if backlog is None:
            self.socket.listen()
        else:
            self.socket.listen(backlog)

    def shutdown(self, how: int) -> None:
        """Shutdown the connection.

        Args:
            how: Flag to indicate which halves of the connection must be shut down.

        See Also:
            :meth:`socket.socket.shutdown`
        """
        self.socket.shutdown(how)

    @property
    def family(self) -> int:
        # pylint: disable=line-too-long
        """The wrapped socket's address family. Usually :const:`socket.AF_INET` (IPv4) or :const:`socket.AF_INET6` (IPv6)."""
        return self.socket.family

    @property
    def type(self) -> int:
        """The wrapped socket's type. Always :const:`socket.SOCK_STREAM`."""
        return self.socket.type

    @property
    def proto(self) -> int:
        """The wrapped socket's protocol number. Usually 0."""
        return self.socket.proto

    def __getattr__(self, attribute):
        if (
            attribute.startswith("recv")
            or attribute.startswith("send")
            or attribute
            in (
                "makefile",
                "share",
                "dup",
            )
        ):
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(
                    self.__class__.__name__, attribute
                )
            )
        warnings.warn(
            "Direct access to the enclosed socket attributes and methods will be removed in version 1.0",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(self.socket, attribute)

    @classmethod
    def create_connection(
        cls,
        address: Tuple,
        timeout: Optional[float] = None,
        source_address: Optional[Tuple] = None,
    ) -> "SlipSocket":
        """Create a SlipSocket connection.

        This convenience method creates a connection to a socket at the specified address
        using the :func:`socket.create_connection` function.
        The socket that is returned from that call is automatically wrapped in
        a :class:`SlipSocket` object.

        Args:
            address (Address): The remote address.
            timeout (float): Optional timeout value.
            source_address (Address): Optional local address for the near socket.

        Returns:
            :class:`~SlipSocket`: A `SlipSocket` that is connected to the socket at the remote address.

        See Also:
            :func:`socket.create_connection`
        """
        sock = socket.create_connection(address[0:2], timeout, source_address)  # type: ignore
        return cls(sock)
