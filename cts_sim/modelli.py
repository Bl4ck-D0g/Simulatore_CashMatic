# Modelli dati del simulatore: tagli, transazioni e scenario di prova.

import copy
import datetime

# Modalita' di erogazione del resto.
RESTO_TUTTO = 0
RESTO_PARZIALE = 1
RESTO_NESSUNO = 2
ERRORE_DISPOSITIVO = 3

ETICHETTE_MODALITA = {
	RESTO_TUTTO: "Resto completo",
	RESTO_PARZIALE: "Resto parziale (circa meta')",
	RESTO_NESSUNO: "Resto non erogato",
	ERRORE_DISPOSITIVO: "Errore dispositivo",
}

# Modalita' di inserimento automatico del contante durante un pagamento.
AUTO_SPENTO = "spento"
AUTO_ESATTO = "esatto"
AUTO_VALORI = "valori"

# Operazioni che accettano contante inserito dall'operatore.
OPERAZIONI_CON_INSERIMENTO = ("payment", "refill", "deposit", "change_denominations")

FORMATO_DATA_LISTA = "%H:%M:%S %d/%m/%Y"
FORMATO_DATA_DETTAGLIO = "%Y-%m-%d %H:%M:%S"
DATA_MINIMA = datetime.datetime(1, 1, 1)


class Denominazione:
	# Un taglio (moneta o banconota) con il relativo instradamento.

	def __init__(self, valore, valuta, tipo, livello, livello_fondo, livello_max, stato, instradamento):
		self.valore = valore
		self.valuta = valuta
		self.tipo = tipo
		self.livello = livello
		self.livello_fondo = livello_fondo
		self.livello_max = livello_max
		self.stato = stato
		self.instradamento = instradamento

	def copia(self):
		return copy.copy(self)

	def come_livello(self):
		# Forma restituita da AllLevels.
		return {
			"value": self.valore,
			"currency": self.valuta,
			"level": self.livello,
			"floatLevel": self.livello_fondo,
			"maxLevel": self.livello_max,
			"type": self.tipo,
			"routing": self.instradamento,
		}

	def come_pezzo_attivo(self):
		# Forma usata da ActiveTransaction e LastTransaction.
		return {
			"value": self.valore,
			"currency": self.valuta,
			"level": self.livello,
			"type": self.tipo,
			"routing": self.instradamento,
		}

	def come_pezzo_report(self):
		# Forma usata da GetTransaction e GetLastTransaction.
		return {
			"value": self.valore,
			"currency": self.valuta,
			"level": self.livello,
			"type": self.tipo,
			"unit": self.tipo,
			"routing": self.instradamento,
		}


class Transazione:
	# Una operazione di cassa (pagamento, ricarica, prelievo, svuotamento...).

	def __init__(self, identificativo, operazione, motivo="", riferimento="", richiesto=0, inserito=0,
				erogato=0, non_erogato=0, timeout=0, mancia=0, origine=""):
		self.identificativo = identificativo
		self.operazione = operazione
		self.motivo = motivo
		self.riferimento = riferimento
		self.richiesto = richiesto
		if mancia:
			self.richiesto = richiesto + mancia
		self.inserito = inserito
		self.erogato = erogato
		self.non_erogato = non_erogato
		self.timeout = timeout
		self.mancia = mancia
		self.valuta = "EUR"
		self.sorgente = "127.0.0.1"
		self.origine = origine
		self.fine = "normal"
		self.stato = "running"
		self.posizione_coda = 0
		self.in_chiusura = False
		self.chiusa = False
		self.inizio = datetime.datetime.now()
		self.ora_fine = DATA_MINIMA
		self.mancanza_corrente = False
		self.pezzi_inseriti = []
		self.pezzi_erogati = []
		self.pezzi_trasferiti = []
		self.istantanea_fine = []

	def _elenco(self, pezzi, forma):
		risultato = []
		for pezzo in pezzi:
			if forma == "attivo":
				risultato.append(pezzo.come_pezzo_attivo())
			else:
				risultato.append(pezzo.come_pezzo_report())
		return risultato

	def come_attiva(self):
		# Forma restituita da ActiveTransaction.
		identificativo = self.identificativo
		if self.operazione == "idle" or self.posizione_coda != 0:
			identificativo = 0
		return {
			"id": identificativo,
			"operation": self.operazione,
			"operationInfo": "",
			"requested": self.richiesto,
			"inserted": self.inserito,
			"dispensed": self.erogato,
			"notDispensed": self.non_erogato,
			"currency": self.valuta,
			"queuePosition": self.posizione_coda,
			"operationPercentage": 0,
			"status": self.stato,
			"denominationsInserted": self._elenco(self.pezzi_inseriti, "attivo"),
			"denominationsDispensed": self._elenco(self.pezzi_erogati, "attivo"),
			# anche questo elenco e' riempito con i pezzi erogati
			"denominationsTransfered": self._elenco(self.pezzi_erogati, "attivo"),
		}

	def come_ultima(self):
		# Forma restituita da LastTransaction.
		return {
			"id": self.identificativo,
			"operation": self.operazione,
			"operationInfo": "",
			"requested": self.richiesto,
			"inserted": self.inserito,
			"dispensed": self.erogato,
			"notDispensed": self.non_erogato,
			"currency": self.valuta,
			"queuePosition": 0,
			"end": self.fine,
			"module": "cash",
			"denominationsInserted": self._elenco(self.pezzi_inseriti, "attivo"),
			"denominationsDispensed": self._elenco(self.pezzi_erogati, "attivo"),
			"denominationsTransfered": self._elenco(self.pezzi_trasferiti, "attivo"),
		}

	def come_record(self, formato_data, con_pezzi):
		# Forma di GetTransactions (senza pezzi) e GetTransaction (con pezzi).
		record = {
			"id": self.identificativo,
			"requested": self.richiesto,
			"inserted": self.inserito,
			"dispensed": self.erogato,
			"notDispensed": self.non_erogato,
			"currency": self.valuta,
			"operation": self.operazione,
			"success": True,
			"endType": self.fine,
			"moduleType": "cash",
			"startTime": self.inizio.strftime(formato_data),
			"endTime": self.ora_fine.strftime(formato_data),
			"source": self.sorgente,
			"reason": self.motivo,
			"reference": self.riferimento,
			"userId": 0,
			"username": "cashmatic",
			"firstName": "Mario",
			"lastName": "Rossi",
			"powerFail": self.mancanza_corrente,
		}
		if con_pezzi:
			record["endSnapshot"] = list(self.istantanea_fine)
			record["piecesIn"] = self._elenco(self.pezzi_inseriti, "report")
			record["piecesOut"] = self._elenco(self.pezzi_erogati, "report")
			record["piecesTransfered"] = self._elenco(self.pezzi_trasferiti, "report")
		return record


class Scenario:
	# Opzioni di prova modificabili dalla GUI (gestione errori e tempi).

	CAMPI = (
		"modalita_resto",
		"ritardo_erogazione_ms",
		"durata_token_min",
		"ritardo_login_min_ms",
		"ritardo_login_max_ms",
		"latenza_extra_ms",
		"percentuale_errori_500",
		"percentuale_connessioni_cadute",
		"mancanza_corrente_prossima",
		"errore_forzato_attivo",
		"errore_forzato_codice",
		"errore_forzato_messaggio",
		"auto_modo",
		"auto_valori",
		"auto_ritardo_ms",
		"porta_aperta",
		"moneta_1_cent",
	)

	def __init__(self):
		self.modalita_resto = RESTO_TUTTO
		self.ritardo_erogazione_ms = 1000
		self.durata_token_min = 15
		self.ritardo_login_min_ms = 1400
		self.ritardo_login_max_ms = 1700
		self.latenza_extra_ms = 0
		self.percentuale_errori_500 = 0
		self.percentuale_connessioni_cadute = 0
		self.mancanza_corrente_prossima = False
		self.errore_forzato_attivo = False
		self.errore_forzato_codice = 4
		self.errore_forzato_messaggio = "Other operation active"
		self.auto_modo = AUTO_SPENTO
		self.auto_valori = "1000"
		self.auto_ritardo_ms = 800
		self.porta_aperta = False
		self.moneta_1_cent = False

	def come_dizionario(self):
		dizionario = {}
		for campo in self.CAMPI:
			dizionario[campo] = getattr(self, campo)
		return dizionario

	def carica(self, dizionario):
		# Applica solo valori del tipo giusto: un profilo malformato non deve
		# lasciare lo scenario con tipi sbagliati.
		nuovi = {}
		for campo in self.CAMPI:
			if campo not in dizionario:
				continue
			valore = dizionario[campo]
			attuale = getattr(self, campo)
			if isinstance(attuale, bool):
				if not isinstance(valore, bool):
					raise ValueError("campo " + campo + ": atteso vero o falso")
			elif isinstance(attuale, int):
				if isinstance(valore, bool) or not isinstance(valore, int):
					raise ValueError("campo " + campo + ": atteso un intero")
			elif not isinstance(valore, str):
				raise ValueError("campo " + campo + ": atteso un testo")
			nuovi[campo] = valore
		for campo, valore in nuovi.items():
			setattr(self, campo, valore)
