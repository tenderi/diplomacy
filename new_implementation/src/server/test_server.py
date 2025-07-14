from .server import Server

def test_server_instantiation():
    server = Server()
    assert server is not None
