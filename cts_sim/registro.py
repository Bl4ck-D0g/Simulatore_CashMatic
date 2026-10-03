# Registro delle richieste: file Log/CS_LOG_gg_mm_aaaa.txt
# e coda di eventi letta dalla GUI.

import datetime
import os
import queue
import re
import threading

LIMITE_EVENTI = 5000
MODELLO_PASSWORD = re.compile(r'("password"\s*:\s*)"(?:[^"\\]|\\.)*"', re.IGNORECASE)


def maschera(testo):
	# Le password del login non vanno scritte in chiaro nel log ne' nella finestra.
	return MODELLO_PASSWORD.sub(r'\1"***"', testo)


class Registro:

	def __init__(self, cartella):
		self.cartella = cartella
		self.eventi = queue.Queue(maxsize=LIMITE_EVENTI)
		self.blocco = threading.Lock()

	def _percorso_file(self):
		nome = datetime.datetime.now().strftime("CS_LOG_%d_%m_%Y.txt")
		return os.path.join(self.cartella, nome)

	def scrivi_richiesta(self, percorso, corpo):
		adesso = datetime.datetime.now()
		ora = adesso.strftime("%H:%M:%S:") + "%04d" % (adesso.microsecond // 100)
		testo = maschera(corpo.strip())
		if not testo:
			testo = "{}"
		riga = ora + " - " + percorso + "\n" + testo + "\n"
		with self.blocco:
			try:
				os.makedirs(self.cartella, exist_ok=True)
				with open(self._percorso_file(), "a", encoding="utf-8") as file:
					file.write(riga)
			except OSError:
				pass

	def notifica(self, evento):
		# Coda a lunghezza limitata: se nessuno la legge (modalita' senza finestra)
		# scarta gli eventi piu' vecchi invece di crescere senza fine.
		while True:
			try:
				self.eventi.put_nowait(evento)
				return
			except queue.Full:
				try:
					self.eventi.get_nowait()
				except queue.Empty:
					pass
