# Motore del dispositivo CashMatic simulato.
# Riproduce la logica del dispositivo: giacenze per taglio,
# inserimento contante, erogazione del resto, svuotamenti, fondo cassa e coda.
#
# Regole di concorrenza: lo stato e' condiviso tra i fili del server, i fili delle
# operazioni e la GUI. Ogni decisione (stato libero, transazione ancora attiva)
# e ogni modifica avvengono sotto self.blocco; le pause restano fuori dal blocco.
# Ogni operazione lavora sulla SUA transazione, passata esplicitamente, e la
# chiusura e' valida una sola volta (chiudi_transazione verifica l'identita').

import datetime
import random
import threading
import time

from . import modelli
from .modelli import Denominazione, Transazione

MOTIVO_STORICO = "Simulator example operation"
OPERAZIONI_STORICO = ("refill", "withdrawal", "payment", "change", "empty_cashbox")
ESITO_OK = (0, "No error")
ESITO_OCCUPATO = (4, "Other operation active")
ESITO_NESSUNA = (5, "No operation active")
ESITO_NON_ESEGUIBILE = (3, "Cannot process command")


class Dispositivo:

	def __init__(self, scenario):
		self.scenario = scenario
		self.blocco = threading.RLock()
		self.fermo = threading.Event()
		self.versione = 0
		self.valuta = "EUR"
		self.fondo_monete = 100
		self.fondo_banconote = 30
		self.max_monete = 1500
		self.max_banconote = 180
		self.max_cashbox = 500
		self.nome = "Cashmatic SelfPay Simulator"
		self.modello = "Cashmatic SelfPay 660"
		self.numero_serie = "0123 66 0123 60 01234"
		self.indirizzo_vpn = "10.0.10.1"
		self.modalita_fiduciaria = False
		self.configurazione = self._configurazione_base()
		self.denominazioni = []
		self.storico = []
		self.coda = []
		self.attiva = None
		self.stato = "idle"
		self.moneta_1_cent_attiva = False
		self.riempi_casuale()
		self.genera_storico(100)
		self._imposta_inattiva()

	# ---------- utilita' di base ----------

	def _configurazione_base(self):
		return {
			"isConfigured": True,
			"language": "it",
			"name": "Cashmatic SelfPay Simulator",
			"useImperialSystem": False,
			"dateTimeFormat": "%H:%M:%S %d/%m/%Y",
			"cashboxValueNotification": 1000,
			"roundChangeAmount": False,
			"lockNotDispensableAmount": False,
			"lockDeviceAlmostEmpty": False,
			"manageSmallCoin": False,
			"timezone": "Europe/Rome",
			"hideDisplaySensitiveData": False,
			"silenceNotificationMinutes": 60,
			"allowUnsafeApi": True,
			"alwaysOn": False,
			"emptyCashboxOnRemove": False,
			"noteInletCapacity": 0,
			"useCashmaticCa": False,
		}

	def notifica(self):
		with self.blocco:
			self.versione += 1

	def attendi(self, secondi):
		self.fermo.wait(secondi)

	def ritardo_erogazione(self):
		return self.scenario.ritardo_erogazione_ms / 1000.0

	def arresta(self):
		# Ferma i fili in corso e chiude l'eventuale operazione attiva, cosi' dopo un
		# riavvio il dispositivo riparte a riposo.
		self.fermo.set()
		with self.blocco:
			self.coda = []
			transazione = self.attiva
			if transazione is not None and transazione.operazione not in ("idle", "initializing"):
				transazione.in_chiusura = True
				transazione.stato = "cancelling"
				transazione.fine = "canceled"
				self.chiudi_transazione(transazione)

	def riprendi(self):
		self.fermo.clear()

	def trova_denominazione(self, valore, instradamento):
		indice = 0
		for denominazione in self.denominazioni:
			if denominazione.valore == valore and denominazione.instradamento == instradamento:
				return indice
			indice += 1
		return -1

	def _registra_pezzo(self, elenco, denominazione, quantita, instradamento):
		for pezzo in elenco:
			if pezzo.valore == denominazione.valore and pezzo.instradamento == instradamento:
				pezzo.livello += quantita
				return
		nuovo = Denominazione(
			denominazione.valore,
			denominazione.valuta,
			denominazione.tipo,
			quantita,
			denominazione.livello_fondo,
			denominazione.livello_max,
			denominazione.stato,
			instradamento,
		)
		elenco.append(nuovo)

	def _in_thread(self, funzione, *argomenti):
		filo = threading.Thread(target=funzione, args=argomenti)
		filo.daemon = True
		filo.start()
		return filo

	# ---------- giacenze ----------

	def _costruisci_livelli(self, casuale):
		generatore = random.Random()
		self.denominazioni = []
		monete = (2, 5, 10, 20, 50, 100, 200)
		for valore in monete:
			livello = 0
			if casuale:
				livello = generatore.randint(self.fondo_monete // 4, self.max_monete // 4)
			self.denominazioni.append(
				Denominazione(valore, self.valuta, "coin", livello, self.fondo_monete, self.max_monete, 1, "recycle")
			)
		banconote = (500, 1000, 2000, 5000)
		for valore in banconote:
			livello = 0
			if casuale:
				livello = generatore.randint(self.fondo_banconote // 4, self.max_banconote // 4)
			self.denominazioni.append(
				Denominazione(valore, self.valuta, "note", livello, self.fondo_banconote, self.max_banconote, 1, "recycle")
			)
		cassaforte = (500, 1000, 2000, 5000, 10000, 20000, 50000)
		for valore in cassaforte:
			livello = 0
			if casuale:
				livello = generatore.randint(0, self.fondo_banconote)
			self.denominazioni.append(
				Denominazione(valore, self.valuta, "note", livello, 0, self.max_cashbox, 1, "cashbox")
			)
		self.moneta_1_cent_attiva = False

	def riempi_casuale(self):
		with self.blocco:
			self._costruisci_livelli(True)
			self.notifica()

	def azzera_livelli(self):
		with self.blocco:
			self._costruisci_livelli(False)
			self.notifica()

	def alterna_moneta_1_cent(self, attiva):
		with self.blocco:
			presente = self.trova_denominazione(1, "recycle") != -1
			if attiva and not presente:
				generatore = random.Random()
				livello = int(generatore.randint(5, int(self.fondo_monete * 0.5)) * 0.25)
				quarto = int(self.fondo_monete * 0.25)
				self.denominazioni.insert(
					0, Denominazione(1, self.valuta, "coin", livello, quarto, quarto, 1, "recycle")
				)
			if not attiva and presente:
				del self.denominazioni[self.trova_denominazione(1, "recycle")]
			self.moneta_1_cent_attiva = attiva
			self.notifica()

	def imposta_livello(self, valore, instradamento, livello):
		with self.blocco:
			indice = self.trova_denominazione(valore, instradamento)
			if indice == -1:
				return False
			self.denominazioni[indice].livello = max(0, int(livello))
			self.notifica()
			return True

	def imposta_stato_taglio(self, valore, instradamento, abilitato):
		with self.blocco:
			indice = self.trova_denominazione(valore, instradamento)
			if indice == -1:
				return False
			self.denominazioni[indice].stato = 1 if abilitato else 0
			self.notifica()
			return True

	def imposta_livelli_fondo(self, elenco):
		with self.blocco:
			for elemento in elenco:
				indice = self.trova_denominazione(elemento["value"], "recycle")
				if indice != -1:
					self.denominazioni[indice].livello_fondo = elemento["level"]
			self.notifica()

	def imposta_livelli_max(self, elenco):
		with self.blocco:
			for elemento in elenco:
				indice = self.trova_denominazione(elemento["value"], "recycle")
				if indice != -1:
					self.denominazioni[indice].livello_max = elemento["level"]
			self.notifica()

	def imposta_stati(self, elenco):
		with self.blocco:
			for elemento in elenco:
				indice = self.trova_denominazione(elemento["value"], "recycle")
				if indice != -1:
					self.denominazioni[indice].stato = 1 if elemento["status"] else 0
			self.notifica()

	def carica_livelli(self, livelli):
		# Costruisce l'elenco in una lista locale: se il profilo e' incompleto
		# le giacenze correnti restano intatte.
		nuove = []
		for voce in livelli:
			try:
				nuove.append(Denominazione(
					int(voce["value"]), voce.get("currency", self.valuta), voce["type"], int(voce["level"]),
					int(voce.get("floatLevel", 0)), int(voce.get("maxLevel", 0)), int(voce.get("status", 1)),
					voce["routing"],
				))
			except (KeyError, TypeError, ValueError, AttributeError):
				raise ValueError("profilo con giacenze incomplete o non valide")
		with self.blocco:
			self.denominazioni = nuove
			self.moneta_1_cent_attiva = self.trova_denominazione(1, "recycle") != -1
			self.notifica()

	def totale_riciclo(self):
		totale = 0
		with self.blocco:
			for denominazione in self.denominazioni:
				if denominazione.instradamento == "recycle":
					totale += denominazione.valore * denominazione.livello
		return totale

	# ---------- storico transazioni ----------

	def genera_storico(self, quantita):
		generatore = random.Random()
		with self.blocco:
			self.storico = []
			for indice in range(quantita):
				operazione = OPERAZIONI_STORICO[generatore.randint(0, len(OPERAZIONI_STORICO) - 1)]
				richiesto = 0
				inserito = 0
				erogato = 0
				non_erogato = 0
				if operazione == "refill":
					inserito = round(generatore.randint(0, 25000) / 10) * 10
				if operazione == "withdrawal":
					richiesto = generatore.randint(0, 15000)
					erogato = richiesto
					if indice % 12 == 0:
						non_erogato = round(generatore.randint(0, 10000) / 10) * 10
						erogato = max(0, richiesto - non_erogato)
				if operazione == "payment":
					richiesto = round(generatore.randint(0, 10000) / 10) * 10
					inserito = richiesto + round(generatore.randint(500, 10000) / 10) * 10
					erogato = inserito - richiesto
					if indice % 14 == 0:
						non_erogato = erogato
						erogato = 0
				if operazione == "change":
					richiesto = round(generatore.randint(0, 10000) / 10) * 10
					inserito = richiesto
					erogato = richiesto
				if operazione == "empty_cashbox":
					richiesto = round(generatore.randint(0, 100000) / 10) * 10
					erogato = richiesto
				transazione = Transazione(
					len(self.storico), operazione, MOTIVO_STORICO, "", richiesto, inserito, erogato, non_erogato
				)
				transazione.chiusa = True
				self.storico.append(transazione)
			self.notifica()

	def trova_storico(self, identificativo):
		with self.blocco:
			if identificativo < 0 or identificativo >= len(self.storico):
				return None
			return self.storico[identificativo]

	# ---------- ciclo di vita delle transazioni ----------

	def _imposta_inattiva(self):
		with self.blocco:
			self.attiva = Transazione(len(self.storico), "idle")
			self.stato = "idle"
			self.notifica()

	def nuova_transazione(self, operazione, motivo="", riferimento="", richiesto=0, timeout=0, mancia=0, origine=""):
		# Crea e rende attiva una transazione. Il controllo "dispositivo libero" lo fa
		# il chiamante sotto lo stesso blocco (vedi _nuova_se_libera).
		with self.blocco:
			transazione = Transazione(
				len(self.storico), operazione, motivo, riferimento, richiesto, 0, 0, 0, timeout, mancia, origine
			)
			self.attiva = transazione
			self.stato = operazione
			self.notifica()
			return transazione

	def _nuova_se_libera(self, operazione, motivo="", riferimento="", richiesto=0, timeout=0, mancia=0, origine=""):
		with self.blocco:
			if self.stato != "idle":
				return None
			return self.nuova_transazione(operazione, motivo, riferimento, richiesto, timeout, mancia, origine)

	def chiudi_transazione(self, transazione=None):
		# Chiude e archivia la transazione indicata. Esce senza fare nulla se non e'
		# piu' quella attiva o se e' gia' stata chiusa (evita doppi archivi).
		with self.blocco:
			attiva = self.attiva
			if attiva is None or attiva.operazione in ("idle", "initializing"):
				return False
			if transazione is not None and attiva is not transazione:
				return False
			if attiva.chiusa:
				return False
			attiva.chiusa = True
			attiva.ora_fine = datetime.datetime.now()
			attiva.istantanea_fine = []
			for denominazione in self.denominazioni:
				attiva.istantanea_fine.append({
					"value": denominazione.valore,
					"currency": denominazione.valuta,
					"level": denominazione.livello,
					"unit": denominazione.tipo,
					"routing": denominazione.instradamento,
				})
			self.storico.append(attiva)
			if len(self.coda) == 0:
				self._imposta_inattiva()
			else:
				prossimo = self.coda.pop(0)
				for altro in self.coda:
					altro["posizione"] -= 1
				self._avvia_pagamento_da_coda(prossimo)
			self.notifica()
			return True

	def _prenota_chiusura(self, transazione):
		# Sotto blocco: segna la transazione come "in chiusura" cosi' una sola
		# azione (annullo, conferma, timeout, fine pagamento) la porta a termine.
		if transazione is None:
			transazione = self.attiva
		if transazione is None or self.attiva is not transazione:
			return None
		if transazione.in_chiusura or transazione.chiusa or transazione.operazione == "idle":
			return None
		transazione.in_chiusura = True
		return transazione

	def annulla_transazione(self, transazione=None, fine="canceled"):
		with self.blocco:
			transazione = self._prenota_chiusura(transazione)
			if transazione is None:
				return False
			inserito = transazione.inserito
		self.eroga_importo(inserito, transazione)
		with self.blocco:
			transazione.stato = "cancelling"
			transazione.fine = fine
		self.chiudi_transazione(transazione)
		return True

	def scadenza_transazione(self, transazione=None):
		return self.annulla_transazione(transazione, "timeout")

	def conferma_transazione(self, transazione=None):
		with self.blocco:
			transazione = self._prenota_chiusura(transazione)
			if transazione is None:
				return False
			transazione.stato = "stopping"
			transazione.fine = "stopped"
		self.chiudi_transazione(transazione)
		return True

	def annulla_cambio(self, transazione=None):
		with self.blocco:
			transazione = self._prenota_chiusura(transazione)
			if transazione is None:
				return False
			inserito = transazione.inserito
		self.eroga_importo(inserito, transazione)
		self.chiudi_transazione(transazione)
		return True

	# ---------- inserimento contante ----------

	def accetta_inserimento(self):
		with self.blocco:
			if self.attiva is None or self.attiva.in_chiusura:
				return False
			return self.attiva.operazione in modelli.OPERAZIONI_CON_INSERIMENTO

	def inserisci_contante(self, valore):
		with self.blocco:
			attiva = self.attiva
			if attiva is None or attiva.operazione not in modelli.OPERAZIONI_CON_INSERIMENTO:
				return False
			if attiva.in_chiusura:
				return False
			instradamento_cassaforte = False
			indice = self.trova_denominazione(valore, "recycle")
			if indice == -1:
				indice = self.trova_denominazione(valore, "cashbox")
				instradamento_cassaforte = True
			if indice == -1:
				return False
			denominazione = self.denominazioni[indice]
			if denominazione.stato == 0:
				return False
			if attiva.operazione == "refill":
				if denominazione.livello < denominazione.livello_fondo and not instradamento_cassaforte:
					denominazione.instradamento = "recycle"
					denominazione.livello += 1
				else:
					return False
			elif instradamento_cassaforte:
				denominazione.livello += 1
			elif denominazione.livello < denominazione.livello_max:
				denominazione.livello += 1
			elif denominazione.tipo == "note":
				indice_cassaforte = self.trova_denominazione(valore, "cashbox")
				if indice_cassaforte == -1:
					return False
				denominazione = self.denominazioni[indice_cassaforte]
				denominazione.livello += 1
			else:
				return False
			self._registra_pezzo(attiva.pezzi_inseriti, denominazione, 1, denominazione.instradamento)
			attiva.inserito += valore
			self.notifica()
			return True

	# ---------- erogazione ----------

	def _miglior_taglio(self, restante):
		migliore = -1
		valore_migliore = 0
		indice = 0
		for denominazione in self.denominazioni:
			if denominazione.instradamento == "recycle" and denominazione.livello > 0 and denominazione.valore <= restante:
				if denominazione.valore > valore_migliore:
					migliore = indice
					valore_migliore = denominazione.valore
			indice += 1
		return migliore

	def eroga_importo(self, importo, transazione=None):
		if transazione is None:
			transazione = self.attiva
		modalita = self.scenario.modalita_resto
		if importo <= 0:
			return
		if modalita == modelli.RESTO_NESSUNO:
			with self.blocco:
				transazione.non_erogato += importo
				self.notifica()
			return
		totale = importo
		restante = importo
		while restante > 0:
			if self.fermo.is_set():
				return
			with self.blocco:
				indice = self._miglior_taglio(restante)
				if modalita == modelli.RESTO_PARZIALE and restante <= totale // 2:
					indice = -1
				if indice == -1:
					transazione.non_erogato += restante
					self.notifica()
					return
			self.attendi(self.ritardo_erogazione())
			with self.blocco:
				denominazione = self.denominazioni[indice]
				if denominazione.livello <= 0:
					continue
				denominazione.livello -= 1
				restante -= denominazione.valore
				self._registra_pezzo(transazione.pezzi_erogati, denominazione, 1, denominazione.instradamento)
				transazione.erogato += denominazione.valore
				self.notifica()

	def eroga_tagli(self, elenco, transazione=None):
		if transazione is None:
			transazione = self.attiva
		modalita = self.scenario.modalita_resto
		totale = 0
		for elemento in elenco:
			totale += elemento["value"] * elemento["level"]
		if modalita == modelli.RESTO_NESSUNO:
			with self.blocco:
				transazione.non_erogato += totale
				self.notifica()
			return
		erogato_qui = 0
		for elemento in elenco:
			for ripetizione in range(elemento["level"]):
				if self.fermo.is_set():
					return
				valore = elemento["value"]
				salta = modalita == modelli.RESTO_PARZIALE and totale - erogato_qui <= totale // 2
				if not salta:
					with self.blocco:
						indice = self.trova_denominazione(valore, "recycle")
						salta = indice == -1 or self.denominazioni[indice].livello <= 0
				if salta:
					with self.blocco:
						transazione.non_erogato += valore
						self.notifica()
					continue
				self.attendi(self.ritardo_erogazione())
				with self.blocco:
					denominazione = self.denominazioni[indice]
					if denominazione.livello <= 0:
						transazione.non_erogato += valore
						self.notifica()
						continue
					denominazione.livello -= 1
					self._registra_pezzo(transazione.pezzi_erogati, denominazione, 1, denominazione.instradamento)
					erogato_qui += valore
					transazione.erogato += valore
					self.notifica()

	def _vale_filtro(self, denominazione, monete, banconote):
		if denominazione.tipo == "coin" and not monete:
			return False
		if denominazione.tipo == "note" and not banconote:
			return False
		return True

	def _sposta_in_cassaforte(self, denominazione, quantita):
		indice = self.trova_denominazione(denominazione.valore, "cashbox")
		if indice == -1:
			self.denominazioni.append(Denominazione(
				denominazione.valore, denominazione.valuta, "note", 0, 0, self.max_cashbox, 1, "cashbox"
			))
			indice = len(self.denominazioni) - 1
		self.denominazioni[indice].livello += quantita

	def _trasferisci(self, transazione, monete, banconote, solo_eccedenza):
		# Svuotamento (tutto il riciclo) o fondo cassa (solo l'eccedenza oltre il fondo):
		# le monete escono, le banconote vanno in cassaforte.
		totale = 0
		with self.blocco:
			for denominazione in self.denominazioni:
				if denominazione.instradamento != "recycle":
					continue
				if not self._vale_filtro(denominazione, monete, banconote):
					continue
				quantita = denominazione.livello
				if solo_eccedenza:
					quantita = denominazione.livello - denominazione.livello_fondo
				if quantita > 0:
					totale += denominazione.valore * quantita
			transazione.richiesto = totale
		if self.scenario.modalita_resto == modelli.RESTO_NESSUNO:
			with self.blocco:
				transazione.non_erogato += totale
				self.notifica()
			return
		restante = totale
		for indice in range(len(self.denominazioni)):
			if self.fermo.is_set():
				return
			with self.blocco:
				denominazione = self.denominazioni[indice]
				quantita = denominazione.livello
				if solo_eccedenza:
					quantita = denominazione.livello - denominazione.livello_fondo
				da_fare = denominazione.instradamento == "recycle" and quantita > 0
				if da_fare:
					da_fare = self._vale_filtro(denominazione, monete, banconote)
			if not da_fare:
				continue
			self.attendi(1.0)
			with self.blocco:
				quantita = denominazione.livello
				if solo_eccedenza:
					quantita = denominazione.livello - denominazione.livello_fondo
				if quantita <= 0:
					continue
				denominazione.livello -= quantita
				if denominazione.tipo == "note":
					self._sposta_in_cassaforte(denominazione, quantita)
				restante -= denominazione.valore * quantita
				transazione.erogato += denominazione.valore * quantita
				if denominazione.tipo == "coin":
					self._registra_pezzo(transazione.pezzi_erogati, denominazione, quantita, "recycle")
				else:
					self._registra_pezzo(transazione.pezzi_trasferiti, denominazione, quantita, "recycle")
				self.notifica()
			if self.scenario.modalita_resto == modelli.RESTO_PARZIALE and restante <= totale // 2:
				with self.blocco:
					transazione.non_erogato += restante
					self.notifica()
				return

	def _svuota_cassaforte(self, transazione, monete, banconote):
		totale = 0
		with self.blocco:
			for denominazione in self.denominazioni:
				if denominazione.instradamento == "cashbox" and self._vale_filtro(denominazione, monete, banconote):
					totale += denominazione.valore * denominazione.livello
			transazione.richiesto = totale
		for indice in range(len(self.denominazioni)):
			if self.fermo.is_set():
				return
			with self.blocco:
				denominazione = self.denominazioni[indice]
				da_fare = denominazione.instradamento == "cashbox" and denominazione.livello > 0
				if da_fare:
					da_fare = self._vale_filtro(denominazione, monete, banconote)
			if not da_fare:
				continue
			self.attendi(self.ritardo_erogazione())
			with self.blocco:
				quantita = denominazione.livello
				self._registra_pezzo(transazione.pezzi_erogati, denominazione, quantita, "cashbox")
				transazione.erogato += denominazione.valore * quantita
				denominazione.livello = 0
				self.notifica()

	# ---------- pagamento ----------

	def richiedi_pagamento(self, importo, coda_ammessa, motivo, riferimento, timeout, mancia, origine):
		# Decisione atomica: avvia il pagamento, lo mette in coda oppure rifiuta.
		# Restituisce (codice, messaggio) come le API.
		with self.blocco:
			if self.stato != "idle":
				attiva = self.attiva
				if attiva.origine != "" and origine != "" and attiva.origine == origine:
					return ESITO_OCCUPATO
				if not coda_ammessa:
					return ESITO_OCCUPATO
				for elemento in self.coda:
					if elemento["origine"] != "" and origine != "" and elemento["origine"] == origine:
						return ESITO_OCCUPATO
				if self.stato != "payment":
					return ESITO_OCCUPATO
				self.coda.append({
					"importo": importo, "motivo": motivo, "riferimento": riferimento, "timeout": timeout,
					"mancia": mancia, "origine": origine, "posizione": len(self.coda) + 1,
				})
				self.notifica()
				return ESITO_OK
			transazione = self.nuova_transazione("payment", motivo, riferimento, importo, timeout, mancia, origine)
			self._avvia_fili_pagamento(transazione)
		return ESITO_OK

	def _avvia_pagamento_da_coda(self, elemento):
		with self.blocco:
			transazione = self.nuova_transazione(
				"payment", elemento["motivo"], elemento["riferimento"], elemento["importo"],
				elemento["timeout"], elemento["mancia"], elemento["origine"]
			)
			self._avvia_fili_pagamento(transazione)

	def _avvia_fili_pagamento(self, transazione):
		if self.scenario.mancanza_corrente_prossima:
			self.scenario.mancanza_corrente_prossima = False
			self._in_thread(self._mancanza_corrente, transazione)
			return
		self._in_thread(self._ciclo_pagamento, transazione)
		if self.scenario.auto_modo != modelli.AUTO_SPENTO:
			self._in_thread(self._inserimento_automatico, transazione)

	def _mancanza_corrente(self, transazione):
		self.attendi(1.0)
		with self.blocco:
			transazione = self._prenota_chiusura(transazione)
			if transazione is None:
				return
			transazione.mancanza_corrente = True
			transazione.inserito = 0
		self.chiudi_transazione(transazione)

	def _ciclo_pagamento(self, transazione):
		inizio = time.monotonic()
		while True:
			if self.fermo.is_set():
				return
			with self.blocco:
				if self.attiva is not transazione or transazione.in_chiusura:
					return
			if transazione.timeout > 0 and time.monotonic() - inizio >= transazione.timeout:
				self.scadenza_transazione(transazione)
				return
			self.attendi(0.2)
			with self.blocco:
				if self.attiva is not transazione or transazione.in_chiusura:
					return
				if transazione.inserito >= transazione.richiesto:
					transazione.in_chiusura = True
					resto = transazione.inserito - transazione.richiesto
					break
		if resto > 0:
			self.eroga_importo(resto, transazione)
		self.chiudi_transazione(transazione)

	def _valori_automatici(self, transazione):
		valori = []
		if self.scenario.auto_modo == modelli.AUTO_VALORI:
			for parte in str(self.scenario.auto_valori).replace(";", ",").split(","):
				parte = parte.strip()
				if parte.isdigit():
					valori.append(int(parte))
			return valori
		restante = transazione.richiesto
		with self.blocco:
			abilitati = []
			for denominazione in self.denominazioni:
				if denominazione.stato == 1 and denominazione.valore not in abilitati:
					abilitati.append(denominazione.valore)
			abilitati.sort(reverse=True)
		for valore in abilitati:
			while restante >= valore:
				valori.append(valore)
				restante -= valore
		if restante > 0:
			for valore in reversed(abilitati):
				if valore >= restante:
					valori.append(valore)
					break
		return valori

	def _inserimento_automatico(self, transazione):
		valori = self._valori_automatici(transazione)
		for valore in valori:
			self.attendi(self.scenario.auto_ritardo_ms / 1000.0)
			with self.blocco:
				if self.attiva is not transazione or self.fermo.is_set() or transazione.in_chiusura:
					return
			self.inserisci_contante(valore)
			if transazione.inserito >= transazione.richiesto:
				return

	def annulla_pagamento_client(self, origine):
		# CancelPayment: un client in coda toglie solo la propria richiesta; il
		# proprietario del pagamento attivo lo annulla (solo se l'importo non e' raggiunto).
		with self.blocco:
			if self.stato != "payment":
				return ESITO_NESSUNA
			attiva = self.attiva
			if origine != "" and attiva.origine != origine:
				for indice in range(len(self.coda)):
					if self.coda[indice]["origine"] == origine:
						del self.coda[indice]
						for resto in range(indice, len(self.coda)):
							self.coda[resto]["posizione"] -= 1
						self.notifica()
						return ESITO_OK
			if attiva.in_chiusura or attiva.inserito >= attiva.richiesto:
				return ESITO_NON_ESEGUIBILE
		self._in_thread(self.annulla_transazione, attiva)
		return ESITO_OK

	def conferma_pagamento_client(self):
		with self.blocco:
			if self.stato != "payment":
				return ESITO_NESSUNA
			attiva = self.attiva
			if attiva.in_chiusura:
				return ESITO_NON_ESEGUIBILE
			if attiva.inserito < attiva.richiesto and attiva.inserito <= 0:
				return ESITO_NON_ESEGUIBILE
		if self.conferma_transazione(attiva):
			return ESITO_OK
		return ESITO_NON_ESEGUIBILE

	def ferma_operazione(self, operazione):
		# StopRefill e StopDeposit.
		with self.blocco:
			if self.stato != operazione:
				return ESITO_NESSUNA
			attiva = self.attiva
		self.chiudi_transazione(attiva)
		return ESITO_OK

	def annulla_cambio_client(self):
		with self.blocco:
			if self.stato != "change_denominations":
				return ESITO_NESSUNA
			attiva = self.attiva
		self.annulla_cambio(attiva)
		return ESITO_OK

	# ---------- operazioni ----------

	def avvia_ricarica(self, motivo, riferimento, origine=""):
		return self._nuova_se_libera("refill", motivo, riferimento, 0, 0, 0, origine)

	def avvia_deposito(self, motivo, riferimento, origine=""):
		return self._nuova_se_libera("deposit", motivo, riferimento, 0, 0, 0, origine)

	def _avvia_con_filo(self, operazione, motivo, riferimento, richiesto, lavoro, *argomenti):
		# Crea la transazione nello stesso blocco del controllo di stato e solo il
		# lavoro lungo gira nel filo.
		transazione = self._nuova_se_libera(operazione, motivo, riferimento, richiesto)
		if transazione is None:
			return None
		self._in_thread(self._esegui, lavoro, transazione, *argomenti)
		return transazione

	def _esegui(self, lavoro, transazione, *argomenti):
		# Il lavoro restituisce False se la transazione e' stata chiusa da un altro filo.
		if lavoro(transazione, *argomenti) is False:
			return
		self.chiudi_transazione(transazione)

	def avvia_prelievo(self, importo, motivo, riferimento):
		return self._avvia_con_filo("withdrawal", motivo, riferimento, importo, self.eroga_importo_di, importo)

	def eroga_importo_di(self, transazione, importo):
		self.eroga_importo(importo, transazione)

	def avvia_prelievo_tagli(self, elenco, motivo, riferimento):
		return self._avvia_con_filo("withdrawal_denominations", motivo, riferimento, 0, self.eroga_tagli_di, elenco)

	def eroga_tagli_di(self, transazione, elenco):
		self.eroga_tagli(elenco, transazione)

	def avvia_cambio_tagli(self, elenco, motivo, riferimento):
		richiesto = 0
		for elemento in elenco:
			richiesto += elemento["value"] * elemento["level"]
		return self._avvia_con_filo("change_denominations", motivo, riferimento, richiesto, self._lavoro_cambio, elenco)

	def _lavoro_cambio(self, transazione, elenco):
		while True:
			if self.fermo.is_set():
				return False
			with self.blocco:
				if self.attiva is not transazione or transazione.in_chiusura:
					return False
				if transazione.inserito >= transazione.richiesto:
					transazione.in_chiusura = True
					break
			self.attendi(0.1)
		self.eroga_tagli(elenco, transazione)
		eccedenza = transazione.inserito - transazione.richiesto
		if eccedenza > 0:
			self.eroga_importo(eccedenza, transazione)

	def avvia_svuota(self, operazione, monete, banconote, motivo, riferimento):
		return self._avvia_con_filo(operazione, motivo, riferimento, 0, self._trasferisci_di, monete, banconote, False)

	def avvia_fondo(self, operazione, monete, banconote, motivo, riferimento):
		return self._avvia_con_filo(operazione, motivo, riferimento, 0, self._trasferisci_di, monete, banconote, True)

	def _trasferisci_di(self, transazione, monete, banconote, solo_eccedenza):
		self._trasferisci(transazione, monete, banconote, solo_eccedenza)

	def avvia_svuota_cassaforte(self, operazione, monete, banconote, motivo, riferimento):
		return self._avvia_con_filo(operazione, motivo, riferimento, 0, self._svuota_cassaforte, monete, banconote)

	def avvia_chiusura_cassa(self, motivo, riferimento):
		return self._avvia_con_filo("register_closure", motivo, riferimento, 0, self._trasferisci_di, True, True, True)

	def importo_chiusura(self):
		totale = 0
		with self.blocco:
			for denominazione in self.denominazioni:
				if denominazione.instradamento == "recycle" and denominazione.livello > denominazione.livello_fondo:
					totale += denominazione.valore * (denominazione.livello - denominazione.livello_fondo)
		return totale
