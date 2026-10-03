# Gestione del certificato TLS del simulatore.

import datetime
import os
import socket
import ssl
import subprocess


def leggi_scadenza(percorso):
	# Restituisce la data di scadenza del certificato oppure None se non leggibile.
	try:
		informazioni = ssl._ssl._test_decode_cert(percorso)
		scadenza = ssl.cert_time_to_seconds(informazioni["notAfter"])
	except (OSError, ValueError, KeyError, AttributeError):
		return None
	return datetime.datetime.fromtimestamp(scadenza)


def e_scaduto(percorso):
	scadenza = leggi_scadenza(percorso)
	if scadenza is None:
		return True
	return scadenza < datetime.datetime.now()


def _indirizzi_locali():
	indirizzi = ["127.0.0.1"]
	try:
		nome = socket.gethostname()
		altri = socket.gethostbyname_ex(nome)[2]
	except OSError:
		altri = []
	for indirizzo in altri:
		if indirizzo not in indirizzi:
			indirizzi.append(indirizzo)
	return indirizzi


def _rimuovi(percorso):
	try:
		os.remove(percorso)
	except OSError:
		pass


def genera_certificato(percorso):
	# Crea un certificato autofirmato valido 10 anni con il comando openssl.
	# Il file finale ha permessi 0600 (contiene la chiave privata) e viene scritto
	# in modo atomico: o resta quello vecchio, o c'e' quello nuovo completo.
	nomi = ["DNS:localhost"]
	for indirizzo in _indirizzi_locali():
		nomi.append("IP:" + indirizzo)
	chiave = percorso + ".chiave.tmp"
	certificato = percorso + ".cert.tmp"
	finale = percorso + ".nuovo.tmp"
	comando = [
		"openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650",
		"-subj", "/CN=localhost", "-addext", "subjectAltName=" + ",".join(nomi),
		"-keyout", chiave, "-out", certificato,
	]
	try:
		try:
			esito = subprocess.run(comando, capture_output=True, text=True, timeout=60)
		except (OSError, subprocess.SubprocessError) as errore:
			return False, "openssl non disponibile: " + str(errore)
		if esito.returncode != 0:
			return False, "openssl ha fallito: " + esito.stderr.strip()
		with open(chiave, "r", encoding="ascii") as file:
			testo_chiave = file.read()
		with open(certificato, "r", encoding="ascii") as file:
			testo_certificato = file.read()
		descrittore = os.open(finale, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
		with os.fdopen(descrittore, "w", encoding="ascii") as file:
			file.write(testo_chiave)
			file.write(testo_certificato)
		os.replace(finale, percorso)
	except OSError as errore:
		return False, "scrittura non riuscita: " + str(errore)
	finally:
		for temporaneo in (chiave, certificato, finale):
			_rimuovi(temporaneo)
	return True, "Certificato rigenerato"
