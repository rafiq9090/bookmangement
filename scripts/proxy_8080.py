import socket
import threading
import sys

def forward(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass

def handle_client(client_sock):
    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.connect(('127.0.0.1', 8000))
        t1 = threading.Thread(target=forward, args=(client_sock, server_sock), daemon=True)
        t2 = threading.Thread(target=forward, args=(server_sock, client_sock), daemon=True)
        t1.start()
        t2.start()
    except Exception:
        try:
            client_sock.close()
        except Exception:
            pass

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(('0.0.0.0', 8080))
    except Exception as e:
        print(f"Error binding to 8080: {e}", file=sys.stderr)
        sys.exit(1)
    s.listen(128)
    print("TCP Proxy listening on 8080 forwarding to 8000", flush=True)
    while True:
        try:
            client, _ = s.accept()
            threading.Thread(target=handle_client, args=(client,), daemon=True).start()
        except Exception:
            break

if __name__ == '__main__':
    main()
