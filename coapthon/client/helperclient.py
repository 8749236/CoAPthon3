import random
from multiprocessing import Queue
from queue import Empty
import threading
from coapthon.messages.message import Message
from coapthon import defines
from coapthon.client.coap import CoAP
from coapthon.messages.request import Request
from coapthon.utils import generate_random_token

__author__ = 'Giacomo Tanganelli'


class HelperClient(object):
    """
    Helper Client class to perform requests to remote servers in a simplified way.
    """
    def __init__(self, server, sock=None, cb_ignore_read_exception=None, cb_ignore_write_exception=None):
        """
        Initialize a client to perform request to a server.

        :param server: the remote CoAP server
        :param sock: if a socket has been created externally, it can be used directly
        :param cb_ignore_read_exception: Callback function to handle exception raised during the socket read operation
        :param cb_ignore_write_exception: Callback function to handle exception raised during the socket write operation 
        """
        self.server = server
        self.protocol = CoAP(self.server, random.randint(1, 65535), self._wait_response, sock=sock,
                             cb_ignore_read_exception=cb_ignore_read_exception, cb_ignore_write_exception=cb_ignore_write_exception)
        self.queue = Queue()
        self.observe_token = None
        self.observe_path = None

    def _wait_response(self, message):
        """
        Private function to get responses from the server.

        :param message: the received message
        """
        if message is None or message.code != defines.Codes.CONTINUE.number:
            self.queue.put(message)

    def stop(self):
        """
        Stop the client.
        """
        self.protocol.close()
        self.queue.put(None)

    def close(self):
        """
        Close the client.
        """
        self.stop()

    def _thread_body(self, request, callback):
        """
        Private function. Send a request, wait for response and call the callback function.

        :param request: the request to send
        :param callback: the callback function
        """
        self.protocol.send_message(request)
        while not self.protocol.stopped.isSet():
            response = self.queue.get(block=True)
            callback(response)
            
    def cancel_observe_token(self, token=None, explicit=False, timeout=None):  # pragma: no cover
        """
        Delete observing on the remote server.

        :param token: the observe token
        :param explicit: if explicitly cancel
        """
        if token is None:
            token = self.observe_token
        if self.observe_token is None:
            return None
        self.protocol.end_observation(token)
        if not explicit:
            self.observe_path = None
            return

        request = self.mk_request(defines.Codes.GET, self.observe_path)

        # RFC7641 explicit cancel is by sending OBSERVE=1 with the same token,
        # not by an unsolicited RST (which would be ignored)
        request.token = token
        request.observe = 1

        resp = self.send_request(request, callback=None, timeout=timeout)
        if resp:
            self.observe_token = None
            self.observe_path = None
        return resp

    def cancel_observing(self, response, explicit):  # pragma: no cover
        """
        Delete observing on the remote server.

        :param response: the last received response
        :param explicit: if explicitly cancel using token
        """
        self.cancel_observe_token(self, response.token, explicit)

    def get(self, path, callback=None, timeout=None, **kwargs):  # pragma: no cover
        """
        Perform a GET on a certain path.

        :param path: the path
        :param callback: the callback function to invoke upon response
        :param timeout: the timeout of the request
        :return: the response
        """
        request = self.mk_request(defines.Codes.GET, path)
        request.token = generate_random_token(2)

        for k, v in kwargs.items():
            if hasattr(request, k):
                setattr(request, k, v)

        return self.send_request(request, callback, timeout)

    def get_non(self, path, callback=None, timeout=None, **kwargs):  # pragma: no cover
        """
        Perform a GET on a certain path.

        :param path: the path
        :param callback: the callback function to invoke upon response
        :param timeout: the timeout of the request
        :return: the response
        """
        request = self.mk_request_non(defines.Codes.GET, path)
        request.token = generate_random_token(2)

        for k, v in kwargs.items():
            if hasattr(request, k):
                setattr(request, k, v)

        return self.send_request(request, callback, timeout)

    def observe(self, path, callback, timeout=None, **kwargs):  # pragma: no cover
        """
        Perform a GET with observe on a certain path.

        :param path: the path
        :param callback: the callback function to invoke upon notifications
        :param timeout: the timeout of the request
        :return: the response to the observe request
        """
        if self.observe_token is not None:
            raise RuntimeError("Only one active observation is allowed per client")
        self.observe_token = generate_random_token(2)
        self.observe_path = path
        request = self.mk_request(defines.Codes.GET, path)
        request.token = self.observe_token
        request.observe = 0

        for k, v in kwargs.items():
            if hasattr(request, k):
                setattr(request, k, v)

        self.send_request(request, callback, timeout)
        return self.observe_token

    def delete(self, path, callback=None, timeout=None, **kwargs):  # pragma: no cover
        """
        Perform a DELETE on a certain path.

        :param path: the path
        :param callback: the callback function to invoke upon response
        :param timeout: the timeout of the request
        :return: the response
        """
        request = self.mk_request(defines.Codes.DELETE, path)

        for k, v in kwargs.items():
            if hasattr(request, k):
                setattr(request, k, v)

        return self.send_request(request, callback, timeout)

    def post(self, path, payload, callback=None, timeout=None, no_response=False, **kwargs):  # pragma: no cover
        """
        Perform a POST on a certain path.

        :param path: the path
        :param payload: the request payload
        :param callback: the callback function to invoke upon response
        :param timeout: the timeout of the request
        :return: the response
        """
        request = self.mk_request(defines.Codes.POST, path)
        request.token = generate_random_token(2)
        request.payload = payload

        if no_response:
            request.add_no_response()
            request.type = defines.Types["NON"]

        for k, v in kwargs.items():
            if hasattr(request, k):
                setattr(request, k, v)

        return self.send_request(request, callback, timeout, no_response=no_response)

    def put(self, path, payload, callback=None, timeout=None, no_response=False, **kwargs):  # pragma: no cover
        """
        Perform a PUT on a certain path.

        :param path: the path
        :param payload: the request payload
        :param callback: the callback function to invoke upon response
        :param timeout: the timeout of the request
        :return: the response
        """
        request = self.mk_request(defines.Codes.PUT, path)
        request.token = generate_random_token(2)
        request.payload = payload

        if no_response:
            request.add_no_response()
            request.type = defines.Types["NON"]

        for k, v in kwargs.items():
            if hasattr(request, k):
                setattr(request, k, v)

        return self.send_request(request, callback, timeout, no_response=no_response)

    def discover(self, callback=None, timeout=None, **kwargs):  # pragma: no cover
        """
        Perform a Discover request on the server.

        :param callback: the callback function to invoke upon response
        :param timeout: the timeout of the request
        :return: the response
        """
        request = self.mk_request(defines.Codes.GET, defines.DISCOVERY_URL)

        for k, v in kwargs.items():
            if hasattr(request, k):
                setattr(request, k, v)

        return self.send_request(request, callback, timeout)

    def send_request(self, request, callback=None, timeout=None, no_response=False):  # pragma: no cover
        """
        Send a request to the remote server.

        :param request: the request to send
        :param callback: the callback function to invoke upon response
        :param timeout: the timeout of the request
        :return: the response (synchronous), or the token (for asynchronous callback)
        """
        if callback is not None:
            thread = threading.Thread(target=self._thread_body, args=(request, callback))
            thread.start()
        else:
            self.protocol.send_message(request)
            if no_response:
                return
            try:
                response = self.queue.get(block=True, timeout=timeout)
            except Empty:
                #if timeout is set
                response = None
            return response

    def send_empty(self, empty):  # pragma: no cover
        """
        Send empty message.

        :param empty: the empty message
        """
        self.protocol.send_message(empty)

    def mk_request(self, method, path):
        """
        Create a request.

        :param method: the CoAP method
        :param path: the path of the request
        :return:  the request
        """
        request = Request()
        request.destination = self.server
        request.code = method.number
        request.uri_path = path
        return request

    def mk_request_non(self, method, path):
        """
        Create a request.

        :param method: the CoAP method
        :param path: the path of the request
        :return:  the request
        """
        request = Request()
        request.destination = self.server
        request.code = method.number
        request.uri_path = path
        request.type = defines.Types["NON"]
        return request


