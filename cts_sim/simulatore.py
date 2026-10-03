# Composizione dei componenti del simulatore (usata dalla GUI, dalla riga di comando e dai test).

import json
import os

from . import certificato
from .api import Api
from .autenticazione import GestoreToken, Utenti
from .dispositivo import Dispositivo
from .modelli import Scenario
from .registro import Registro
from .server import ServerSimulatore

PORTA_PREDEFINITA = 50301


class Simulatore:

	def __init__(self, cartella_base):
		self.cartella_base = cartella_base
		self.percorso_certificato = os.path.join(cartella_base, "certificati", "server.pem")
		self.cartella_profili = os.path.join(cartella_base, "profili")
		self.scenario = Scenario()
		self.dispositivo = Dispositivo(self.scenario)
		self.utenti = Utenti(os.path.join(cartella_base, "utenti.json"))
		self.gestore_token = GestoreToken(self.scenario)
		self.registro = Registro(os.path.join(cartella_base, "Log"))
		self.api = Api(self.dispositivo, self.scenario, self.gestore_token, self.utenti, self.registro)
		self.server = ServerSimulatore(self.api, self.scenario, self.registro)

	def avvia_server(self, porta=PORTA_PREDEFINITA, https=True, indirizzo="0.0.0.0"):
		self.dispositivo.riprendi()
		self.server.avvia(porta, https, self.percorso_certificato, indirizzo)

	def ferma_server(self):
		self.dispositivo.arresta()
		self.server.ferma()

	def certificato_scaduto(self):
		return certificato.e_scaduto(self.percorso_certificato)

	def rigenera_certificato(self):
		return certificato.genera_certificato(self.percorso_certificato)

	def salva_profilo(self, percorso):
		livelli = []
		with self.dispositivo.blocco:
			for denominazione in self.dispositivo.denominazioni:
				livelli.append(denominazione.come_livello())
				livelli[-1]["status"] = denominazione.stato
		contenuto = {"scenario": self.scenario.come_dizionario(), "livelli": livelli}
		with open(percorso, "w", encoding="utf-8") as file:
			json.dump(contenuto, file, indent=2)

	def carica_profilo(self, percorso):
		with open(percorso, "r", encoding="utf-8") as file:
			contenuto = json.load(file)
		if not isinstance(contenuto, dict):
			raise ValueError("profilo non valido")
		# Prima si convalidano le giacenze, poi si applica tutto: un profilo
		# difettoso non lascia il simulatore a meta'.
		livelli = contenuto.get("livelli", [])
		scenario = contenuto.get("scenario", {})
		if not isinstance(scenario, dict) or not isinstance(livelli, list):
			raise ValueError("profilo non valido")
		prova = Scenario()
		prova.carica(scenario)
		if livelli:
			self.dispositivo.carica_livelli(livelli)
		self.scenario.carica(scenario)
