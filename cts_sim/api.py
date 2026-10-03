# Livello API REST del simulatore: rotte, verbi, controlli e codici di risposta
# (aree User, Device, Transaction, Report, Settings, Door, Utility, update).

import datetime
import json
import math
import random
import time

from . import modelli
from . import risposte


class ErroreRichiesta(Exception):
	pass


class Risposta:

	def __init__(self, stato, corpo=b"", intestazioni=None):
		self.stato = stato
		self.corpo = corpo
		self.intestazioni = intestazioni or {}


def _intero(dati, chiave, predefinito=0):
	valore = dati.get(chiave)
	if valore is None:
		return predefinito
	if isinstance(valore, bool):
		raise ErroreRichiesta(chiave)
	if isinstance(valore, int):
		return valore
	if isinstance(valore, float) and math.isfinite(valore) and valore == int(valore):
		return int(valore)
	raise ErroreRichiesta(chiave)


def _testo(dati, chiave):
	valore = dati.get(chiave)
	if valore is None:
		return ""
	if not isinstance(valore, str):
		raise ErroreRichiesta(chiave)
	return valore


def _booleano(dati, chiave, predefinito=False):
	valore = dati.get(chiave)
	if valore is None:
		return predefinito
	if not isinstance(valore, bool):
		raise ErroreRichiesta(chiave)
	return valore


def _elenco_tagli(dati, chiave="denominations"):
	valore = dati.get(chiave)
	if valore is None:
		return None
	if not isinstance(valore, list):
		raise ErroreRichiesta(chiave)
	risultato = []
	for voce in valore:
		if not isinstance(voce, dict):
			raise ErroreRichiesta(chiave)
		valore_taglio = _intero(voce, "value")
		livello = _intero(voce, "level")
		if valore_taglio <= 0 or livello < 0:
			raise ErroreRichiesta(chiave)
		risultato.append({
			"value": valore_taglio,
			"currency": _testo(voce, "currency"),
			"level": livello,
			"type": _testo(voce, "type"),
			"status": _booleano(voce, "status", True),
		})
	return risultato


class Api:

	def __init__(self, dispositivo, scenario, gestore_token, utenti, registro):
		self.dispositivo = dispositivo
		self.scenario = scenario
		self.gestore_token = gestore_token
		self.utenti = utenti
		self.registro = registro
		self.rotte = {}
		self._costruisci_rotte()

	# ---------- tabella delle rotte ----------

	def _rotta(self, percorso, metodo, funzione, autenticata=True):
		self.rotte[percorso] = (metodo, funzione, autenticata)

	def _costruisci_rotte(self):
		self._rotta("/api/user/Login", "POST", self._login, False)
		self._rotta("/api/user/RenewToken", "POST", self._rinnova_token)
		self._rotta("/api/user/Details", "POST", self._dettagli_utente)
		self._rotta("/api/user/GetAll", "POST", self._tutti_utenti)
		self._rotta("/api/user/Update", "POST", self._aggiorna_utente)
		self._rotta("/api/device/GetDeviceInfo", "POST", self._info_dispositivo)
		self._rotta("/api/device/AllLevels", "POST", self._tutti_livelli)
		self._rotta("/api/device/ActiveTransaction", "POST", self._transazione_attiva)
		self._rotta("/api/device/LastTransaction", "POST", self._ultima_transazione)
		self._rotta("/api/transaction/StartRefill", "POST", self._avvia_ricarica)
		self._rotta("/api/transaction/StopRefill", "POST", self._ferma_ricarica)
		self._rotta("/api/transaction/StartPayment", "POST", self._avvia_pagamento)
		self._rotta("/api/transaction/CancelPayment", "POST", self._annulla_pagamento)
		self._rotta("/api/transaction/CommitPayment", "POST", self._conferma_pagamento)
		self._rotta("/api/transaction/StartWithdrawal", "POST", self._avvia_prelievo)
		self._rotta("/api/transaction/StartEmptyAll", "POST", self._svuota_tutto)
		self._rotta("/api/transaction/StartEmptyCoins", "POST", self._svuota_monete)
		self._rotta("/api/transaction/StartEmptyNotes", "POST", self._svuota_banconote)
		self._rotta("/api/transaction/StartFloatAll", "POST", self._fondo_tutto)
		self._rotta("/api/transaction/StartFloatCoins", "POST", self._fondo_monete)
		self._rotta("/api/transaction/StartFloatNotes", "POST", self._fondo_banconote)
		self._rotta("/api/transaction/StartEmptyCashboxAll", "POST", self._cassaforte_tutto)
		self._rotta("/api/transaction/StartEmptyCashboxCoins", "POST", self._cassaforte_monete)
		self._rotta("/api/transaction/StartEmptyCashboxNotes", "POST", self._cassaforte_banconote)
		self._rotta("/api/transaction/StartWithdrawalDenominations", "POST", self._prelievo_tagli)
		self._rotta("/api/transaction/StartChangeDenominations", "POST", self._cambio_tagli)
		self._rotta("/api/transaction/CancelChange", "POST", self._annulla_cambio)
		self._rotta("/api/transaction/StartDeposit", "POST", self._avvia_deposito)
		self._rotta("/api/transaction/StopDeposit", "POST", self._ferma_deposito)
		self._rotta("/api/transaction/StartRegisterClosure", "POST", self._avvia_chiusura)
		self._rotta("/api/transaction/RegisterClosureAmount", "GET", self._importo_chiusura)
		self._rotta("/api/transaction/RegisterClosureDetails", "GET", self._dettagli_chiusura)
		self._rotta("/api/report/GetTransactions", "POST", self._report_transazioni)
		self._rotta("/api/report/GetLastTransaction", "POST", self._report_ultima)
		self._rotta("/api/report/GetTransaction", "POST", self._report_transazione)
		self._rotta("/api/report/ResetCountability", "POST", self._azzera_contabilita)
		self._rotta("/api/report/GetCountability", "POST", self._leggi_contabilita)
		self._rotta("/api/report/GetConfig", "POST", self._config_report)
		base = "/api/settings/denomination/"
		self._rotta(base + "GetSettableMaxLevelCoins", "POST", self._livelli_impostabili("max", "coin"))
		self._rotta(base + "GetSettableMaxLevelNotes", "POST", self._livelli_impostabili("max", "note"))
		self._rotta(base + "GetSettableFloatLevelCoins", "POST", self._livelli_impostabili("fondo", "coin"))
		self._rotta(base + "GetSettableFloatLevelNotes", "POST", self._livelli_impostabili("fondo", "note"))
		self._rotta(base + "SetFloatLevelCoins", "POST", self._imposta_livelli("fondo"))
		self._rotta(base + "SetFloatLevelNotes", "POST", self._imposta_livelli("fondo"))
		self._rotta(base + "SetMaxLevelCoins", "POST", self._imposta_livelli("max"))
		self._rotta(base + "SetMaxLevelNotes", "POST", self._imposta_livelli("max"))
		self._rotta(base + "GetCoinDenominationStatus", "POST", self._stati_tagli("coin"))
		self._rotta(base + "GetNoteDenominationStatus", "POST", self._stati_tagli("note"))
		self._rotta(base + "SetCoinDenominationStatus", "POST", self._imposta_stati_tagli)
		self._rotta(base + "SetNoteDenominationStatus", "POST", self._imposta_stati_tagli)
		self._rotta("/api/settings/device/StartParking", "POST", self._parcheggio)
		self._rotta("/api/settings/device/GetConfig", "POST", self._leggi_config)
		self._rotta("/api/settings/device/SetConfig", "POST", self._scrivi_config)
		self._rotta("/api/settings/device/GetTrustedModeStatus", "POST", self._leggi_modalita_fiduciaria)
		self._rotta("/api/settings/device/SetTrustedMode", "POST", self._scrivi_modalita_fiduciaria)
		self._rotta("/api/door/Available", "POST", self._porta_disponibile)
		self._rotta("/api/door/Status", "POST", self._porta_stato)
		self._rotta("/api/door/Open", "POST", self._porta_apri)
		self._rotta("/api/utility/Poweroff", "POST", self._spegni)
		self._rotta("/api/utility/Reboot", "POST", self._riavvia)
		self._rotta("/api/update/OS/CheckUpdate", "POST", self._aggiornamento_semplice)
		self._rotta("/api/update/OS/DownloadUpdate", "POST", self._aggiornamento_semplice)
		self._rotta("/api/update/OS/InstallUpdate", "POST", self._aggiornamento_semplice)
		self._rotta("/api/update/OS/GetUpdateStatus", "POST", self._stato_aggiornamento)

	# ---------- elaborazione di una richiesta ----------

	def elabora(self, metodo, bersaglio, intestazioni, corpo, ip):
		testo_corpo = corpo.decode("utf-8", errors="replace")
		percorso = bersaglio.split("?")[0]
		self.registro.scrivi_richiesta(bersaglio, testo_corpo)
		voce = self.rotte.get(percorso)
		if voce is None or "?" in bersaglio:
			return Risposta(404)
		metodo_atteso, funzione, autenticata = voce
		if metodo != metodo_atteso:
			return Risposta(405, b"", {"Allow": metodo_atteso})
		if autenticata and not self._token_valido(intestazioni):
			return Risposta(401)
		try:
			dati = self._leggi_json(testo_corpo)
			esito = funzione(dati, ip)
		except ErroreRichiesta:
			return Risposta(400)
		except Exception as errore:
			# Un errore imprevisto non deve far morire il filo senza risposta.
			self.registro.notifica({"tipo": "errore", "testo": percorso + ": " + repr(errore)})
			return Risposta(500)
		if isinstance(esito, Risposta):
			return esito
		return self._risposta(esito[0], esito[1], esito[2])

	def _leggi_json(self, testo):
		if not testo.strip():
			return {}
		try:
			dati = json.loads(testo)
		except (ValueError, RecursionError):
			raise ErroreRichiesta("json")
		if dati is None:
			return {}
		if not isinstance(dati, dict):
			raise ErroreRichiesta("json")
		return dati

	def _token_valido(self, intestazioni):
		autorizzazione = intestazioni.get("Authorization", "")
		token = autorizzazione.replace("Bearer ", "")
		if not token or not token.isascii():
			return False
		return self.gestore_token.valida(token) is not None

	def _risposta(self, codice, messaggio, dati=None):
		corpo = {"code": codice, "message": messaggio}
		if dati is not None:
			corpo["data"] = dati
		testo = json.dumps(corpo, separators=(",", ":"))
		return Risposta(200, testo.encode("utf-8"))

	def _ok(self, dati=None):
		return (0, "No error", dati)

	# ---------- utenti ----------

	def _login(self, dati, ip):
		nome = _testo(dati, "username")
		password = _testo(dati, "password")
		utente = self.utenti.per_nome(nome)
		if utente is None:
			return (11, "User not found", None)
		if utente["password"] != password:
			return (12, "User Invalid Password", None)
		token = self.gestore_token.genera(nome + password)
		minimo = self.scenario.ritardo_login_min_ms
		massimo = max(minimo, self.scenario.ritardo_login_max_ms)
		if massimo > 0:
			time.sleep(random.randint(minimo, massimo) / 1000.0)
		return self._ok({"token": token, "refreshToken": "", "type": 0})

	def _rinnova_token(self, dati, ip):
		token = self.gestore_token.genera("cashmaticadmin")
		return self._ok({"token": token})

	def _dettagli_utente(self, dati, ip):
		identificativo = _intero(dati, "id", 0)
		utente = self.utenti.per_id(identificativo)
		if utente is None:
			return (11, "User not found", None)
		return self._ok(risposte.dettagli_utente(utente))

	def _tutti_utenti(self, dati, ip):
		self.utenti.carica()
		elenco = []
		for utente in self.utenti.elenco:
			elenco.append(risposte.elenco_utente(utente))
		return self._ok(elenco)

	def _aggiorna_utente(self, dati, ip):
		return self._ok()

	# ---------- dispositivo ----------

	def _errore_dispositivo(self):
		return self.scenario.modalita_resto == modelli.ERRORE_DISPOSITIVO

	def _info_dispositivo(self, dati, ip):
		return self._ok(risposte.info_dispositivo(self.dispositivo, self._errore_dispositivo()))

	def _tutti_livelli(self, dati, ip):
		livelli = []
		with self.dispositivo.blocco:
			for denominazione in self.dispositivo.denominazioni:
				livelli.append(denominazione.come_livello())
		return self._ok(livelli)

	def _transazione_attiva(self, dati, ip):
		dispositivo = self.dispositivo
		with dispositivo.blocco:
			attiva = dispositivo.attiva
			if ip and attiva.origine != ip:
				for elemento in dispositivo.coda:
					if elemento["origine"] == ip:
						attiva = modelli.Transazione(
							len(dispositivo.storico), "payment", elemento["motivo"], elemento["riferimento"],
							elemento["importo"], 0, 0, 0, elemento["timeout"], elemento["mancia"], ip
						)
						attiva.posizione_coda = elemento["posizione"]
						break
			return self._ok(attiva.come_attiva())

	def _ultima_transazione(self, dati, ip):
		with self.dispositivo.blocco:
			ultima = self.dispositivo.storico[-1]
			return self._ok(ultima.come_ultima())

	# ---------- avvio operazioni ----------

	def _verifica_avvio(self):
		if self.scenario.errore_forzato_attivo:
			return (self.scenario.errore_forzato_codice, self.scenario.errore_forzato_messaggio, None)
		if self._errore_dispositivo():
			return (6, "Device error", None)
		if self.dispositivo.stato != "idle":
			return (4, "Other operation active", None)
		return None

	def _avvia_ricarica(self, dati, ip):
		errore = self._verifica_avvio()
		if errore:
			return errore
		if self.dispositivo.avvia_ricarica(_testo(dati, "reason"), _testo(dati, "reference"), ip) is None:
			return (4, "Other operation active", None)
		return self._ok()

	def _ferma_ricarica(self, dati, ip):
		esito = self.dispositivo.ferma_operazione("refill")
		return (esito[0], esito[1], None)

	def _avvia_deposito(self, dati, ip):
		errore = self._verifica_avvio()
		if errore:
			return errore
		if self.dispositivo.avvia_deposito(_testo(dati, "reason"), _testo(dati, "reference"), ip) is None:
			return (4, "Other operation active", None)
		return self._ok()

	def _ferma_deposito(self, dati, ip):
		esito = self.dispositivo.ferma_operazione("deposit")
		return (esito[0], esito[1], None)

	def _avvia_pagamento(self, dati, ip):
		importo = _intero(dati, "amount", 0)
		coda_ammessa = _booleano(dati, "queueAllowed")
		motivo = _testo(dati, "reason")
		riferimento = _testo(dati, "reference")
		timeout = _intero(dati, "timeout", 0)
		mancia = _intero(dati, "tipsAmount", 0)
		if self.scenario.errore_forzato_attivo:
			return (self.scenario.errore_forzato_codice, self.scenario.errore_forzato_messaggio, None)
		if self._errore_dispositivo():
			return (6, "Device error", None)
		if importo < 0 or timeout < 0 or mancia < 0:
			return (2, "Invalid parameters", None)
		esito = self.dispositivo.richiedi_pagamento(importo, coda_ammessa, motivo, riferimento, timeout, mancia, ip)
		return (esito[0], esito[1], None)

	def _annulla_pagamento(self, dati, ip):
		esito = self.dispositivo.annulla_pagamento_client(ip)
		return (esito[0], esito[1], None)

	def _conferma_pagamento(self, dati, ip):
		esito = self.dispositivo.conferma_pagamento_client()
		return (esito[0], esito[1], None)

	def _avvia_prelievo(self, dati, ip):
		errore = self._verifica_avvio()
		if errore:
			return errore
		importo = _intero(dati, "amount", 0)
		if importo < 0:
			return (2, "Invalid parameters", None)
		if self.dispositivo.avvia_prelievo(importo, _testo(dati, "reason"), _testo(dati, "reference")) is None:
			return (4, "Other operation active", None)
		return self._ok()

	def _operazione_semplice(self, funzione, argomenti, dati):
		errore = self._verifica_avvio()
		if errore:
			return errore
		if funzione(*argomenti, _testo(dati, "reason"), _testo(dati, "reference")) is None:
			return (4, "Other operation active", None)
		return self._ok()

	def _svuota_tutto(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_svuota, ("empty", True, True), dati)

	def _svuota_monete(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_svuota, ("empty_coins", True, False), dati)

	def _svuota_banconote(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_svuota, ("empty_notes", False, True), dati)

	def _fondo_tutto(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_fondo, ("float", True, True), dati)

	def _fondo_monete(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_fondo, ("float_coins", True, False), dati)

	def _fondo_banconote(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_fondo, ("float_notes", False, True), dati)

	def _cassaforte_tutto(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_svuota_cassaforte, ("cashbox", True, True), dati)

	def _cassaforte_monete(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_svuota_cassaforte, ("cashbox_coins", True, False), dati)

	def _cassaforte_banconote(self, dati, ip):
		return self._operazione_semplice(self.dispositivo.avvia_svuota_cassaforte, ("cashbox_notes", False, True), dati)

	def _avvia_chiusura(self, dati, ip):
		errore = self._verifica_avvio()
		if errore:
			return errore
		if self.dispositivo.avvia_chiusura_cassa(_testo(dati, "reason"), _testo(dati, "reference")) is None:
			return (4, "Other operation active", None)
		return self._ok()

	def _prelievo_tagli(self, dati, ip):
		errore = self._verifica_avvio()
		if errore:
			return errore
		tagli = _elenco_tagli(dati)
		if tagli is None:
			raise ErroreRichiesta("denominations")
		for taglio in tagli:
			with self.dispositivo.blocco:
				indice = self.dispositivo.trova_denominazione(taglio["value"], "recycle")
				if indice == -1:
					raise ErroreRichiesta("denominations")
				if taglio["level"] > self.dispositivo.denominazioni[indice].livello:
					return (8, "No denominations", None)
		if self.dispositivo.avvia_prelievo_tagli(tagli, _testo(dati, "reason"), _testo(dati, "reference")) is None:
			return (4, "Other operation active", None)
		return self._ok()

	def _cambio_tagli(self, dati, ip):
		errore = self._verifica_avvio()
		if errore:
			return errore
		tagli = _elenco_tagli(dati)
		if tagli is None:
			tagli = []
		if self.dispositivo.avvia_cambio_tagli(tagli, _testo(dati, "reason"), _testo(dati, "reference")) is None:
			return (4, "Other operation active", None)
		return self._ok()

	def _annulla_cambio(self, dati, ip):
		esito = self.dispositivo.annulla_cambio_client()
		return (esito[0], esito[1], None)

	def _importo_chiusura(self, dati, ip):
		if self._errore_dispositivo():
			return (6, "Device error", None)
		importo = self.dispositivo.importo_chiusura()
		return self._ok({"amount": importo, "currency": self.dispositivo.valuta})

	def _dettagli_chiusura(self, dati, ip):
		if self._errore_dispositivo():
			return (6, "Device error", None)
		dispositivo = self.dispositivo
		pagamenti = 0
		resto_non_erogato = 0
		ricaricato = 0
		depositato = 0
		prelevato = 0
		fondo = 0
		with dispositivo.blocco:
			for transazione in dispositivo.storico:
				if transazione.operazione == "payment":
					pagamenti += transazione.richiesto
					resto_non_erogato += transazione.non_erogato
				if transazione.operazione == "refill":
					ricaricato += transazione.inserito
				if transazione.operazione == "deposit":
					depositato += transazione.inserito
				if transazione.operazione == "withdrawal":
					prelevato += transazione.erogato
			for denominazione in dispositivo.denominazioni:
				if denominazione.instradamento == "recycle":
					fondo += denominazione.valore * denominazione.livello_fondo
		attuale = dispositivo.totale_riciclo()
		return self._ok({
			"currency": dispositivo.valuta,
			"payments": pagamenti,
			"changeNotDispensed": resto_non_erogato,
			"refilled": ricaricato,
			"deposited": depositato,
			"withdrawn": prelevato,
			"floatLevel": fondo,
			"floatLast": attuale,
			"floatDifference": attuale - fondo,
		})

	# ---------- report ----------

	def _operazione_scelta(self, operazione, filtro):
		corrispondenze = {"register_closure": "deposit"}
		chiave = corrispondenze.get(operazione, operazione)
		if chiave not in risposte.CHIAVI_OPERAZIONI_REPORT:
			return False
		return filtro.get(chiave) is True

	def _data_filtro(self, testo):
		for formato in (modelli.FORMATO_DATA_DETTAGLIO, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
			try:
				return datetime.datetime.strptime(testo, formato)
			except ValueError:
				continue
		return modelli.DATA_MINIMA

	def _report_transazioni(self, dati, ip):
		filtro = dati.get("operations")
		if not isinstance(filtro, dict):
			filtro = {}
		inizio = self._data_filtro(_testo(dati, "startTime"))
		elenco = []
		with self.dispositivo.blocco:
			for transazione in self.dispositivo.storico:
				if not self._operazione_scelta(transazione.operazione, filtro):
					continue
				if inizio > transazione.inizio:
					continue
				elenco.append(transazione.come_record(modelli.FORMATO_DATA_LISTA, False))
		return self._ok(elenco)

	def _report_ultima(self, dati, ip):
		with self.dispositivo.blocco:
			ultima = self.dispositivo.storico[-1]
			return self._ok(ultima.come_record(modelli.FORMATO_DATA_LISTA, True))

	def _report_transazione(self, dati, ip):
		identificativo = _intero(dati, "transactionId", 0)
		transazione = self.dispositivo.trova_storico(identificativo)
		if transazione is None:
			transazione = modelli.Transazione(0, "", "", "", 0, 0, 0, 0)
			transazione.inizio = datetime.datetime.now()
			transazione.ora_fine = datetime.datetime.now()
			transazione.sorgente = ""
		return self._ok(transazione.come_record(modelli.FORMATO_DATA_DETTAGLIO, True))

	def _azzera_contabilita(self, dati, ip):
		return self._ok()

	def _leggi_contabilita(self, dati, ip):
		return self._ok(risposte.contabilita(self.dispositivo.valuta))

	def _config_report(self, dati, ip):
		return self._ok({"pdfConfig": {"orientation": "portrait", "fontSize": 10, "enabledColumns": []}})

	# ---------- impostazioni ----------

	def _livelli_impostabili(self, grandezza, tipo):
		def gestore(dati, ip):
			elenco = []
			with self.dispositivo.blocco:
				for denominazione in self.dispositivo.denominazioni:
					if denominazione.tipo != tipo or denominazione.instradamento != "recycle":
						continue
					livello = denominazione.livello_max
					if grandezza == "fondo":
						livello = denominazione.livello_fondo
					elenco.append({"value": denominazione.valore, "currency": denominazione.valuta, "level": livello})
			return self._ok({"denominations": elenco})
		return gestore

	def _imposta_livelli(self, grandezza):
		def gestore(dati, ip):
			if self.dispositivo.stato != "idle":
				return (4, "Other operation active", None)
			tagli = _elenco_tagli(dati)
			if tagli is None:
				tagli = []
			if grandezza == "fondo":
				self.dispositivo.imposta_livelli_fondo(tagli)
			else:
				self.dispositivo.imposta_livelli_max(tagli)
			return self._ok()
		return gestore

	def _stati_tagli(self, tipo):
		def gestore(dati, ip):
			elenco = []
			with self.dispositivo.blocco:
				for denominazione in self.dispositivo.denominazioni:
					if denominazione.tipo != tipo or denominazione.instradamento != "recycle":
						continue
					elenco.append({
						"value": denominazione.valore,
						"currency": denominazione.valuta,
						"status": denominazione.stato == 1,
					})
			return self._ok({"denominations": elenco})
		return gestore

	def _imposta_stati_tagli(self, dati, ip):
		tagli = _elenco_tagli(dati)
		if tagli is None:
			tagli = []
		self.dispositivo.imposta_stati(tagli)
		return self._ok()

	def _parcheggio(self, dati, ip):
		return self._ok()

	def _leggi_config(self, dati, ip):
		return self._ok(risposte.configurazione(self.dispositivo))

	def _scrivi_config(self, dati, ip):
		with self.dispositivo.blocco:
			for chiave in self.dispositivo.configurazione:
				if chiave not in dati:
					continue
				if type(dati[chiave]) is not type(self.dispositivo.configurazione[chiave]):
					raise ErroreRichiesta(chiave)
			for chiave in self.dispositivo.configurazione:
				if chiave in dati:
					self.dispositivo.configurazione[chiave] = dati[chiave]
		return self._ok()

	def _leggi_modalita_fiduciaria(self, dati, ip):
		return self._ok({"enabled": self.dispositivo.modalita_fiduciaria})

	def _scrivi_modalita_fiduciaria(self, dati, ip):
		self.dispositivo.modalita_fiduciaria = _booleano(dati, "enabled")
		return self._ok()

	# ---------- porta, utilita', aggiornamenti ----------

	def _porta_disponibile(self, dati, ip):
		return self._ok({"main": True, "drawer": False})

	def _porta_stato(self, dati, ip):
		return self._ok({"main": self.scenario.porta_aperta, "drawer": False})

	def _porta_apri(self, dati, ip):
		if _booleano(dati, "drawer"):
			return (7, "User not allowed", None)
		if _booleano(dati, "main"):
			self.scenario.porta_aperta = True
			self.dispositivo.notifica()
		return self._ok()

	def _spegni(self, dati, ip):
		self.registro.notifica({"tipo": "utility", "testo": "Richiesto spegnimento (Poweroff)"})
		return self._ok()

	def _riavvia(self, dati, ip):
		self.registro.notifica({"tipo": "utility", "testo": "Richiesto riavvio (Reboot)"})
		return self._ok()

	def _aggiornamento_semplice(self, dati, ip):
		return self._ok()

	def _stato_aggiornamento(self, dati, ip):
		return self._ok(risposte.stato_aggiornamento())
