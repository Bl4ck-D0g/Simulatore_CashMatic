# Server HTTP/HTTPS del simulatore, basato solo sulla libreria standard.
# Imita le intestazioni del dispositivo reale (server nginx/1.10.3, CORS aperto,
# nessun Content-Type) e applica le opzioni di errore scelte dalla GUI.

import http.server
import random
import socket
import socketserver
import ssl
import sys
import threading
import time

from .registro import maschera

LIMITE_CORPO = 1024 * 1024


class GestoreRichieste(http.server.BaseHTTPRequestHandler):
	protocol_version = "HTTP/1.1"
	server_version = "nginx/1.10.3"
	sys_version = ""
	timeout = 30

	def version_string(self):
		return self.server_version

	def log_message(self, formato, *argomenti):
		return

	def setup(self):
		contesto = self.server.contesto_tls
		if contesto is not None:
			self.request.settimeout(10)
			self.request = contesto.wrap_socket(self.request, server_side=True)
		self.server.registra_connessione(self.request)
		super().setup()

	def finish(self):
		self.server.rimuovi_connessione(self.request)
		try:
			super().finish()
		except OSError:
			pass

	def handle(self):
		try:
			super().handle()
		except (ssl.SSLError, OSError):
			self.close_connection = True

	def _corpo_richiesta(self):
		# Restituisce il corpo, oppure None se la richiesta non e' accettabile.
		if self.headers.get("Transfer-Encoding"):
			return None
		lunghezza = self.headers.get("Content-Length")
		if not lunghezza:
			return b""
		try:
			quanti = int(lunghezza)
		except ValueError:
			return None
		if quanti < 0 or quanti > LIMITE_CORPO:
			return None
		return self.rfile.read(quanti)

	def _rifiuta(self, stato):
		self.send_response(stato)
		self._intestazioni_cors()
		self.send_header("Content-Length", "0")
		self.send_header("Connection", "close")
		self.end_headers()
		self.close_connection = True

	def _intestazioni_cors(self):
		self.send_header("Access-Control-Allow-Origin", "*")

	def _gestisci(self):
		inizio = time.monotonic()
		corpo = self._corpo_richiesta()
		if corpo is None:
			self._rifiuta(413)
			return
		scenario = self.server.scenario
		ip = self.client_address[0]
		if scenario.latenza_extra_ms > 0:
			time.sleep(scenario.latenza_extra_ms / 1000.0)
		if random.random() * 100 < scenario.percentuale_connessioni_cadute:
			self.server.registro.notifica(self._evento(corpo, 0, inizio, "connessione interrotta"))
			self.close_connection = True
			return
		if random.random() * 100 < scenario.percentuale_errori_500:
			risposta_stato = 500
			risposta_corpo = b""
			intestazioni = {}
		else:
			risposta = self.server.api.elabora(self.command, self.path, dict(self.headers.items()), corpo, ip)
			risposta_stato = risposta.stato
			risposta_corpo = risposta.corpo
			intestazioni = risposta.intestazioni
		self.send_response(risposta_stato)
		self._intestazioni_cors()
		for nome, valore in intestazioni.items():
			self.send_header(nome, valore)
		self.send_header("Content-Length", str(len(risposta_corpo)))
		self.end_headers()
		if risposta_corpo:
			self.wfile.write(risposta_corpo)
		self.server.registro.notifica(self._evento(corpo, risposta_stato, inizio, risposta_corpo.decode("utf-8", "replace")))

	def _evento(self, corpo, stato, inizio, risposta):
		return {
			"tipo": "richiesta",
			"ora": time.strftime("%H:%M:%S"),
			"metodo": self.command,
			"percorso": self.path,
			"ip": self.client_address[0],
			"corpo": maschera(corpo.decode("utf-8", "replace")),
			"stato": stato,
			"durata_ms": int((time.monotonic() - inizio) * 1000),
			"risposta": risposta,
		}

	def do_POST(self):
		self._gestisci()

	def do_GET(self):
		self._gestisci()

	def do_PUT(self):
		self._gestisci()

	def do_DELETE(self):
		self._gestisci()

	def do_PATCH(self):
		self._gestisci()

	def do_OPTIONS(self):
		if self._corpo_richiesta() is None:
			self._rifiuta(413)
			return
		self.send_response(204)
		self._intestazioni_cors()
		self.send_header("Access-Control-Allow-Methods", "*")
		richiesti = self.headers.get("Access-Control-Request-Headers", "*")
		self.send_header("Access-Control-Allow-Headers", richiesti)
		self.send_header("Content-Length", "0")
		self.end_headers()


class ServerHttp(socketserver.ThreadingMixIn, http.server.HTTPServer):
	daemon_threads = True
	allow_reuse_address = True

	def __init__(self, *argomenti, **opzioni):
		self.connessioni = set()
		self.blocco_connessioni = threading.Lock()
		super().__init__(*argomenti, **opzioni)

	def registra_connessione(self, connessione):
		with self.blocco_connessioni:
			self.connessioni.add(connessione)

	def rimuovi_connessione(self, connessione):
		with self.blocco_connessioni:
			self.connessioni.discard(connessione)

	def chiudi_connessioni(self):
		with self.blocco_connessioni:
			aperte = list(self.connessioni)
			self.connessioni.clear()
		for connessione in aperte:
			try:
				connessione.shutdown(socket.SHUT_RDWR)
			except OSError:
				pass
			try:
				connessione.close()
			except OSError:
				pass

	def handle_error(self, request, client_address):
		# Errori di handshake TLS (client senza HTTPS, certificato rifiutato): niente
		# traceback, solo una riga nel registro della finestra.
		errore = sys.exc_info()[1]
		if not isinstance(errore, (ssl.SSLError, OSError)):
			super().handle_error(request, client_address)
			return
		motivo = str(errore)
		if "HTTP_REQUEST" in motivo:
			motivo = "il client usa HTTP ma il server e' in HTTPS (usa https:// oppure avvia con --http)"
		self.registro.notifica({
			"tipo": "richiesta",
			"ora": time.strftime("%H:%M:%S"),
			"metodo": "TLS",
			"percorso": "(handshake non riuscito)",
			"ip": client_address[0],
			"corpo": "",
			"stato": 0,
			"durata_ms": 0,
			"risposta": motivo,
		})


class ServerSimulatore:

	def __init__(self, api, scenario, registro):
		self.api = api
		self.scenario = scenario
		self.registro = registro
		self.server = None
		self.filo = None
		self.porta = 0
		self.https = True

	def attivo(self):
		return self.server is not None

	def avvia(self, porta, https, percorso_certificato, indirizzo="0.0.0.0"):
		if self.server is not None:
			return
		contesto = None
		if https:
			contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
			contesto.load_cert_chain(percorso_certificato)
		server = ServerHttp((indirizzo, porta), GestoreRichieste)
		server.api = self.api
		server.scenario = self.scenario
		server.registro = self.registro
		server.contesto_tls = contesto
		self.server = server
		self.porta = server.server_address[1]
		self.https = https
		self.filo = threading.Thread(target=server.serve_forever, daemon=True)
		self.filo.start()

	def ferma(self):
		if self.server is None:
			return
		self.server.shutdown()
		self.server.server_close()
		self.server.chiudi_connessioni()
		self.server = None
		self.filo = None

	def indirizzo(self):
		protocollo = "https"
		if not self.https:
			protocollo = "http"
		return protocollo + "://127.0.0.1:" + str(self.porta) + "/api"
