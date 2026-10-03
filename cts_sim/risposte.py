# Costruttori dei blocchi JSON restituiti dalle API (nomi e struttura come nelle
# risposte del dispositivo reale).

import datetime

CHIAVI_PERMESSI = (
	("general", True), ("opRefill", True), ("opWithdrawal", True), ("opChange", True),
	("opFloatCoins", True), ("opFloatNotes", True), ("opFloatAll", True), ("opEmptyCoins", True),
	("opEmptyNotes", True), ("opEmptyAll", True), ("opEmptyCashboxCoins", False), ("opEmptyCashboxNotes", True),
	("opEmptyCashboxAll", False), ("opPayment", True), ("opWithdrawalDenominations", True), ("opDeposit", True),
	("opRegisterClosure", True), ("report", True), ("settIp", False), ("settReLevels", False),
	("settFloatLevels", True), ("settMaxLevels", True), ("settDenominations", True), ("settMail", False),
	("settPrinter", False), ("settDevice", False), ("settParking", False), ("log", False),
	("usrAdd", False), ("usrEdit", False), ("usrManagePassword", False), ("update", False),
	("reboot", True), ("shutdown", True), ("manageDevice", False), ("openDoor", True),
)

CHIAVI_CAUSALI = (
	"refill", "withdrawal", "change", "floatCoins", "floatNotes", "floatAll", "emptyCashboxCoins",
	"emptyCashboxNotes", "emptyCashboxAll", "payment", "withdrawalDenominations", "deposit",
	"emptyCoins", "emptyNotes", "emptyAll", "registerClosure",
)

CHIAVI_NOTIFICHE = (
	"refill", "withdrawal", "deposit", "emptyCashbox", "cashboxRemoved", "highLevel", "lowLevel", "errors",
)

CHIAVI_OPERAZIONI_REPORT = (
	"cashbox", "cashbox_coins", "cashbox_notes", "change_denominations", "correct_level", "empty",
	"empty_coins", "empty_notes", "float", "float_coins", "float_notes", "payment", "refill",
	"withdrawal", "withdrawal_denominations", "deposit", "register_closure", "service", "empty_disappeared",
)


def _insieme_falso(chiavi):
	risultato = {}
	for chiave in chiavi:
		risultato[chiave] = False
	return risultato


def permessi():
	risultato = {}
	for chiave, valore in CHIAVI_PERMESSI:
		risultato[chiave] = valore
	return risultato


def dettagli_utente(utente):
	return {
		"id": utente["id"],
		"enabled": True,
		"username": utente["username"],
		"firstName": "first name",
		"lastName": "last name",
		"email": "email@cashmatic.it",
		"language": "it",
		"permissions": permessi(),
		"causals": _insieme_falso(CHIAVI_CAUSALI),
		"emails": _insieme_falso(CHIAVI_NOTIFICHE),
		"notifications": _insieme_falso(CHIAVI_NOTIFICHE),
		"notificationsEndpoint": {"email": True, "app": True},
	}


def elenco_utente(utente):
	# GetAll: scrive sempre id 0 e usa lo username come nome e cognome.
	nome = utente["username"]
	return {
		"id": 0,
		"enabled": True,
		"username": nome,
		"firstName": nome,
		"lastName": nome,
		"email": nome + "@cashmatic.it",
		"language": "it",
		"permissions": permessi(),
		"causals": _insieme_falso(CHIAVI_CAUSALI[:15]),
		"emails": _insieme_falso(CHIAVI_NOTIFICHE),
	}


def _modulo(codice, nome_codice, seriale, firmware, billset):
	return {
		"code": codice,
		"nameCode": nome_codice,
		"serialNumber": seriale,
		"firmware": firmware,
		"billset": billset,
		"isActive": True,
		"errorCodes": [],
		"coveredSensors": [],
	}


def _periferica(codice, nome, operativita_codice, operativita, moduli):
	return {
		"nameCode": codice,
		"name": nome,
		"operationalityCode": operativita_codice,
		"operationalityMessage": operativita,
		"statusCode": 0,
		"statusMessage": "none",
		"modules": moduli,
	}


def info_dispositivo(dispositivo, errore):
	if errore:
		stato_codice = 3
		stato_messaggio = "out of service"
		errore_codice = 1
		errore_messaggio = "check peripherals"
		stato_monete = 3
		stato_monete_testo = "out of service"
		nome_pelicano = "Pelicano"
		hopper_codice = 0
		hopper_testo = "detached"
	else:
		stato_codice = 2
		stato_messaggio = dispositivo.stato
		errore_codice = 0
		errore_messaggio = "none"
		stato_monete = 2
		stato_monete_testo = "operational"
		nome_pelicano = "PE"
		hopper_codice = 1
		hopper_testo = "online"
	monete = {
		"typeCode": 0,
		"typeMessage": "coins",
		"statusCode": stato_monete,
		"statusMessage": stato_monete_testo,
		"peripherals": [
			_periferica(0, nome_pelicano, 1, "online", [_modulo(1, "PELICANO", "123456789", "2.19", "")]),
			_periferica(1, "Smart Hopper", hopper_codice, hopper_testo, [_modulo(3, "SH0004", "1234567", "SH000412302561C01", "")]),
		],
	}
	banconote = {
		"typeCode": 0,
		"typeMessage": "notes",
		"statusCode": 2,
		"statusMessage": "operational",
		"peripherals": [
			_periferica(0, "SPO", 1, "online", [
				_modulo(6, "NVS200", "1234567", "NVS20004005251100400", "EUR01035"),
				_modulo(7, "PAYOUT_V3", "1234567", "", ""),
			]),
		],
	}
	return {
		"deviceName": dispositivo.nome,
		"model": dispositivo.modello,
		"serialNumber": dispositivo.numero_serie,
		"vpnAddress": dispositivo.indirizzo_vpn,
		"statusCode": stato_codice,
		"statusMessage": stato_messaggio,
		"errorCode": errore_codice,
		"errorMessage": errore_messaggio,
		"functionalityCode": 0,
		"functionalityMessage": "deactivated",
		"modules": [monete, banconote],
	}


def configurazione(dispositivo):
	dati = dict(dispositivo.configurazione)
	dati["timezoneAvailable"] = ["Europe/Rome", "Europe/London", "UTC"]
	dati["dateTimeFormatAvailable"] = ["%H:%M:%S %d/%m/%Y", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"]
	return dati


def stato_aggiornamento():
	return {
		"status": "ready",
		"updateFound": False,
		"lastCheck": datetime.datetime.now().strftime("%I:%M:%S %d/%m/%Y"),
		"version": "16",
		"downloadProgress": 0,
		"currentUpdateVersion": 15,
		"changelog": "",
	}


def contabilita(valuta):
	# GetCountability restituisce valori di esempio fissi.
	return {
		"currency": valuta,
		"last": {
			"startTime": "sample starttime", "endTime": "sample endtime", "paymentInserted": 0,
			"paymentDispensed": 1, "paymentNotDispensed": 2, "paymentIncome": 3, "refilled": 4,
			"withdrawn": 5, "cashboxWithdrawn": 6,
		},
		"current": {
			"startTime": "sample starttime", "endTime": "sample endtime", "paymentInserted": 0,
			"paymentDispensed": 1, "paymentNotDispensed": 2, "paymentIncome": 3, "refilled": 4,
			"withdrawn": 5, "cashboxWithdrawn": 6, "deposit": 7,
		},
	}
