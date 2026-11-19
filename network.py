"""Local discovery, one-shot authenticated delivery. No credential logging."""
import hashlib
import socket
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, Zeroconf

from secure_protocol import handshake

SERVICE_TYPE = '_kpcsend._tcp.local.'
PORT = 43187


@dataclass
class Nearby:
    instance: str
    host: str
    ip: str
    port: int
    ident: str


class Signals(QObject):
    discovered = Signal(object)
    question = Signal(object)
    delivered = Signal(str)
    failure = Signal(str)


class Answer:
    def __init__(self, kind, title, details, timeout=45):
        self.kind = kind
        self.title = title
        self.details = details
        self.event = threading.Event()
        self.accepted = False
        self.timeout = timeout

    def wait(self, signals):
        signals.question.emit(self)
        if not self.event.wait(self.timeout):
            return False
        return self.accepted


class Discovery:
    def __init__(self, signals, identity_key, label):
        self.signals = signals
        self.identifier = hashlib.sha256(identity_key).hexdigest()[:16]
        self.label = label
        self.lock = threading.Lock()
        self.nearby = {}
        self.zc = Zeroconf(ip_version=IPVersion.V4Only)
        instance = f'KeePassLAN-{socket.gethostname()}-{self.identifier}.{SERVICE_TYPE}'
        self.info = ServiceInfo(SERVICE_TYPE, instance,
                                addresses=self._addresses(), port=PORT,
                                properties={b'id': self.identifier.encode('ascii'), b'host': label.encode('utf-8')},
                                server=f'{socket.gethostname()}.local.')
        self.zc.register_service(self.info)
        self.browser = ServiceBrowser(self.zc, SERVICE_TYPE, self)

    @staticmethod
    def _addresses():
        ips = set()
        try:
            for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = result[4][0]
                if not ip.startswith(('127.', '169.254.')):
                    ips.add(ip)
        except socket.gaierror:
            pass
        try:
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                if not ip.startswith(('127.', '169.254.')):
                    ips.add(ip)
        except socket.gaierror:
            pass
        if not ips:
            raise RuntimeError('No se encontró una dirección IPv4 válida de la red.')
        return [socket.inet_aton(ip) for ip in sorted(ips)]

    def add_service(self, zc, type_, name):
        self.update_service(zc, type_, name)

    def update_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name, timeout=1500)
        if not info:
            return
        identifier = info.properties.get(b'id', b'').decode('ascii', errors='ignore')
        if identifier == self.identifier or len(identifier) != 16:
            return
        ips = info.parsed_addresses()
        if not ips:
            return
        host = info.properties.get(b'host', b'Equipo').decode('utf-8', errors='replace')
        with self.lock:
            self.nearby[name] = Nearby(name, host[:64], ips[0], info.port, identifier)
            snapshot = list(self.nearby.values())
        self.signals.discovered.emit(snapshot)

    def remove_service(self, zc, type_, name):
        with self.lock:
            self.nearby.pop(name, None)
            snapshot = list(self.nearby.values())
        self.signals.discovered.emit(snapshot)

    def close(self):
        self.zc.unregister_service(self.info)
        self.zc.close()


class TransferService:
    def __init__(self, signals, identity, name, trust):
        self.signals = signals
        self.identity = identity
        self.name = name
        self.trust = trust
        self.running = True
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('0.0.0.0', PORT))
        self.server.listen(16)
        self.server.settimeout(1)
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while self.running:
            try:
                conn, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._incoming, args=(conn,), daemon=True).start()

    def _authorize(self, hs):
        trusted_name = self.trust.get(hs.peer_key)
        if trusted_name is None:
            dialog = Answer('pair', f'Emparejar con {hs.peer_name}',
                            f'Comprueba por teléfono o en persona que ambos equipos muestran '
                            f'EXACTAMENTE este código:\n\n{hs.sas}\n\n'
                            f'Confirma solo si coincide en los dos equipos.', timeout=60)
            local_accept = dialog.wait(self.signals)
        else:
            local_accept = True
        hs.channel.send({'type': 'pair', 'ok': local_accept})
        response = hs.channel.recv()
        if response.get('type') != 'pair' or response.get('ok') is not True or not local_accept:
            raise PermissionError('Emparejamiento rechazado o caducado.')
        if trusted_name is None:
            self.trust.add(hs.peer_key, hs.peer_name)
        return hs.channel

    def _incoming(self, conn):
        with conn:
            conn.settimeout(70)
            try:
                hs = handshake(conn, self.identity, self.name, is_client=False)
                channel = self._authorize(hs)
                offer = channel.recv()
                if offer.get('type') != 'offer' or not isinstance(offer.get('label'), str):
                    raise ValueError('Solicitud no válida.')
                label = offer['label'][:80]
                confirm = Answer('receive', '¿Aceptar una contraseña?',
                                 f'{hs.peer_name} quiere enviarte una contraseña.\n'
                                 f'Referencia: {label}\n\n'
                                 'Al aceptar, se copiará a tu portapapeles (20 segundos).')
                accepted = confirm.wait(self.signals)
                channel.send({'type': 'decision', 'ok': accepted})
                if not accepted:
                    return
                content = channel.recv()
                if content.get('type') != 'secret' or not isinstance(content.get('value'), str):
                    raise ValueError('El mensaje recibido no es válido.')
                if not content['value'] or len(content['value'].encode('utf-8')) > 8192:
                    raise ValueError('Contenido vacío o demasiado largo.')
                paste = Answer('clipboard', 'Guardar contraseña', content['value'], timeout=10)
                success = paste.wait(self.signals)
                channel.send({'type': 'result', 'ok': success})
                if success:
                    self.signals.delivered.emit(f'Contraseña de {hs.peer_name} lista para pegar (20 s).')
            except (OSError, ValueError, PermissionError, ConnectionError, TimeoutError, KeyError) as exc:
                self.signals.failure.emit(f'Recepción: {type(exc).__name__}: {exc}')
            except Exception as exc:
                self.signals.failure.emit(f'Recepción fallida ({type(exc).__name__}).')

    def send_secret(self, peer, label, secret):
        threading.Thread(target=self._outgoing, args=(peer, label, secret), daemon=True).start()

    def _outgoing(self, peer, label, secret):
        try:
            if not secret or len(secret.encode('utf-8')) > 8192:
                raise ValueError('Selecciona un texto de hasta 8192 bytes.')
            with socket.create_connection((peer.ip, peer.port), timeout=8) as conn:
                conn.settimeout(70)
                hs = handshake(conn, self.identity, self.name, is_client=True)
                # Bind peer identity to the mDNS device identifier, not only to a display name.
                received_id = hashlib.sha256(__import__('base64').b64decode(hs.peer_key)).hexdigest()[:16]
                if received_id != peer.ident:
                    raise PermissionError('La identidad del equipo no coincide con el anuncio de red.')
                channel = self._authorize(hs)
                channel.send({'type': 'offer', 'label': label[:80]})
                decision = channel.recv()
                if decision.get('type') != 'decision' or decision.get('ok') is not True:
                    self.signals.delivered.emit('El destinatario ha rechazado la solicitud.')
                    return
                channel.send({'type': 'secret', 'value': secret})
                result = channel.recv()
                if result.get('type') != 'result' or result.get('ok') is not True:
                    raise RuntimeError('No se pudo escribir en el portapapeles remoto.')
                self.signals.delivered.emit('Transferencia completada. El receptor ya puede pegar.')
        except Exception as exc:
            self.signals.failure.emit(f'Envío: {type(exc).__name__}: {exc}')

    def close(self):
        self.running = False
        self.server.close()
