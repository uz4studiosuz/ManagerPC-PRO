"""TLS transport shared by the service and the visible desktop companion."""
import hashlib
import http.client
import json
import ssl
from pathlib import Path
from urllib.parse import urlsplit


def request(config, path, payload, timeout=8):
    url = urlsplit(config['server'])
    if url.scheme != 'https' or not url.hostname:
        raise ValueError('Xavfsiz HTTPS ulanish kerak. Agentni yangi paketdan o‘rnating.')
    certificate = Path(config['certificate'])
    pem = certificate.read_text(encoding='ascii')
    fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()
    if fingerprint != config['fingerprint']:
        raise ValueError('Server sertifikati o‘zgargan. Agent paketini qayta oling.')
    context = ssl.create_default_context(cafile=str(certificate))
    context.check_hostname = False  # Trust the exact bundled certificate, independent of LAN IP.
    connection = http.client.HTTPSConnection(url.hostname, url.port or 8766, context=context, timeout=timeout)
    try:
        connection.connect()
        actual = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
        if actual != fingerprint:
            raise ValueError('Server sertifikati mos kelmadi')
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        connection.request('POST', path, body, {'Content-Type': 'application/json'})
        response = connection.getresponse()
        raw = response.read(4 * 1024 * 1024)
        result = json.loads(raw)
        if response.status != 200:
            raise ValueError(result.get('error', 'Server xatosi'))
        return result
    finally:
        connection.close()


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def make_certificate(directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime
    directory = Path(directory)
    cert_path, key_path = directory / 'server-cert.pem', directory / 'server-key.pem'
    if not cert_path.exists() or not key_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'ManagerPC local server')])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(days=1))
                .not_valid_after(now + datetime.timedelta(days=3650))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .sign(key, hashes.SHA256()))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert_path.read_text())).hexdigest()
    return cert_path, key_path, fingerprint
