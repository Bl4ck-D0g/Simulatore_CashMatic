# Utenti e token JWT HS256.

import base64
import hashlib
import hmac
import json
import threading
import time

CHIAVE_BASE64 = "ERMN05OPLoDvbTTa/QkqLNMI7cPLguaRyHzyg7n5qNBVjQmtBhz4SzYh4NBVCXi3KJHlSXKP+oi2+bXr6CUYTR=="
CLAIM_NOME = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"


def _codifica(dati):
	return base64.urlsafe_b64encode(dati).rstrip(b"=").decode("ascii")


def _decodifica(testo):
	riempimento = "=" * (-len(testo) % 4)
	return base64.urlsafe_b64decode(testo + riempimento)


class Utenti:
	# Elenco utenti letto da utenti.json (id, username, password).

	def __init__(self, percorso):
		self.percorso = percorso
		self.elenco = []
		self.carica()

	def carica(self):
		try:
			with open(self.percorso, "r", encoding="utf-8") as file:
				contenuto = json.load(file)
		except (OSError, ValueError):
			contenuto = []
		nuovo = []
		for voce in contenuto:
			nuovo.append({
				"id": voce.get("id", 0),
				"username": voce.get("username", ""),
				"password": voce.get("password", ""),
			})
		self.elenco = nuovo

	def per_nome(self, nome):
		for utente in self.elenco:
			if utente["username"] == nome:
				return utente
		return None

	def per_id(self, identificativo):
		for utente in self.elenco:
			if utente["id"] == identificativo:
				return utente
		return None


class GestoreToken:

	def __init__(self, scenario):
		self.scenario = scenario
		self.chiave = base64.b64decode(CHIAVE_BASE64)
		self.revocati = set()
		self.ultimo = ""
		self.blocco = threading.Lock()

	def genera(self, nome):
		adesso = int(time.time())
		intestazione = {"alg": "HS256", "typ": "JWT"}
		scadenza = adesso + int(self.scenario.durata_token_min) * 60
		contenuto = {CLAIM_NOME: nome, "nbf": adesso, "exp": scadenza, "iat": adesso}
		parte_uno = _codifica(json.dumps(intestazione, separators=(",", ":")).encode("utf-8"))
		parte_due = _codifica(json.dumps(contenuto, separators=(",", ":")).encode("utf-8"))
		firma = hmac.new(self.chiave, (parte_uno + "." + parte_due).encode("ascii"), hashlib.sha256).digest()
		token = parte_uno + "." + parte_due + "." + _codifica(firma)
		with self.blocco:
			self.ultimo = token
		return token

	def valida(self, token):
		# Restituisce il nome dell'utente oppure None se il token non e' valido.
		with self.blocco:
			if token in self.revocati:
				return None
		parti = token.split(".")
		if len(parti) != 3:
			return None
		try:
			firma_attesa = hmac.new(self.chiave, (parti[0] + "." + parti[1]).encode("ascii"), hashlib.sha256).digest()
			firma_ricevuta = _decodifica(parti[2])
			contenuto = json.loads(_decodifica(parti[1]).decode("utf-8"))
		except (ValueError, UnicodeError):
			return None
		if not isinstance(contenuto, dict):
			return None
		if not hmac.compare_digest(firma_attesa, firma_ricevuta):
			return None
		if contenuto.get("exp", 0) <= time.time():
			return None
		return contenuto.get(CLAIM_NOME)

	def revoca(self, token):
		with self.blocco:
			self.revocati.add(token)

	def revoca_ultimo(self):
		with self.blocco:
			ultimo = self.ultimo
		if ultimo:
			self.revoca(ultimo)
		return ultimo

	def pulisci_revocati(self):
		with self.blocco:
			self.revocati.clear()
