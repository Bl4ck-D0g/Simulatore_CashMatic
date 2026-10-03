# Prove del simulatore: avviano il server su una porta libera (senza TLS) e
# verificano rotte, codici di errore e flussi di pagamento.
# Esecuzione: python3 -m unittest discover -s tests -v

import http.client
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cts_sim import modelli
from cts_sim.simulatore import Simulatore

CARTELLA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BaseProva(unittest.TestCase):

	def setUp(self):
		self.sim = Simulatore(CARTELLA)
		self.sim.registro.cartella = tempfile.mkdtemp()
		self.sim.scenario.ritardo_erogazione_ms = 5
		self.sim.scenario.ritardo_login_min_ms = 0
		self.sim.scenario.ritardo_login_max_ms = 0
		self.sim.avvia_server(0, False)
		self.token = self.chiama("/api/user/Login", {"username": "cashmatic", "password": "admin"}, None)[2]["data"]["token"]

	def tearDown(self):
		self.sim.ferma_server()

	def chiama(self, percorso, corpo=None, token="auto", metodo="POST"):
		if token == "auto":
			token = self.token
		connessione = http.client.HTTPConnection("127.0.0.1", self.sim.server.porta, timeout=10)
		intestazioni = {}
		testo = None
		if corpo is not None:
			testo = json.dumps(corpo)
			intestazioni["Content-Type"] = "application/json"
		if token:
			intestazioni["Authorization"] = "Bearer " + token
		connessione.request(metodo, percorso, testo, intestazioni)
		risposta = connessione.getresponse()
		contenuto = risposta.read()
		dati = None
		if contenuto:
			dati = json.loads(contenuto)
		stato = risposta.status
		intest = dict(risposta.getheaders())
		connessione.close()
		return stato, intest, dati

	def codice(self, percorso, corpo=None):
		return self.chiama(percorso, corpo)[2]["code"]

	def attendi_inattivo(self, secondi=10):
		fine = time.time() + secondi
		while time.time() < fine:
			if self.sim.dispositivo.stato == "idle":
				return
			time.sleep(0.05)
		self.fail("il dispositivo non e' tornato idle")

	def ultima(self):
		return self.chiama("/api/device/LastTransaction", {})[2]["data"]


class ProveRotte(BaseProva):

	def test_login_errori(self):
		self.assertEqual(self.chiama("/api/user/Login", {"username": "cashmatic", "password": "x"}, None)[2]["code"], 12)
		self.assertEqual(self.chiama("/api/user/Login", {"username": "nessuno", "password": "x"}, None)[2]["code"], 11)

	def test_intestazioni_e_stati_http(self):
		stato, intest, dati = self.chiama("/api/device/AllLevels", {})
		self.assertEqual(stato, 200)
		self.assertEqual(intest.get("Server"), "nginx/1.10.3")
		self.assertEqual(intest.get("Access-Control-Allow-Origin"), "*")
		self.assertNotIn("Content-Type", intest)
		self.assertEqual(self.chiama("/api/device/AllLevels", {}, None)[0], 401)
		self.assertEqual(self.chiama("/api/device/AllLevels", {}, "falso")[0], 401)
		self.assertEqual(self.chiama("/api/non/esiste", {})[0], 404)
		self.assertEqual(self.chiama("/api/device/AllLevels?x=1", {})[0], 404)
		stato, intest, dati = self.chiama("/api/device/AllLevels", None, metodo="GET")
		self.assertEqual(stato, 405)
		self.assertEqual(intest.get("Allow"), "POST")

	def test_livelli_e_attiva_inattiva(self):
		livelli = self.chiama("/api/device/AllLevels", {})[2]["data"]
		self.assertEqual(len(livelli), 18)
		attiva = self.chiama("/api/device/ActiveTransaction", {})[2]["data"]
		self.assertEqual(attiva["operation"], "idle")
		self.assertEqual(attiva["id"], 0)
		self.assertEqual(attiva["status"], "running")

	def test_dettagli_utente_e_info_dispositivo(self):
		dettagli = self.chiama("/api/user/Details", {"id": 0})[2]
		self.assertEqual(dettagli["data"]["username"], "cashmatic")
		self.assertEqual(self.chiama("/api/user/Details", {"id": 99})[2]["code"], 11)
		info = self.chiama("/api/device/GetDeviceInfo", {})[2]["data"]
		self.assertEqual(info["statusMessage"], "idle")
		self.assertEqual(len(info["modules"]), 2)

	def test_rinnovo_token_e_revoca(self):
		nuovo = self.chiama("/api/user/RenewToken", {})[2]["data"]["token"]
		self.assertEqual(self.chiama("/api/device/AllLevels", {}, nuovo)[0], 200)
		self.sim.gestore_token.revoca(self.token)
		self.assertEqual(self.chiama("/api/device/AllLevels", {})[0], 401)

	def test_json_non_valido(self):
		connessione = http.client.HTTPConnection("127.0.0.1", self.sim.server.porta, timeout=10)
		connessione.request("POST", "/api/transaction/StartPayment", "{rotto", {"Authorization": "Bearer " + self.token})
		self.assertEqual(connessione.getresponse().status, 400)
		connessione.close()

	def test_report(self):
		storico = self.chiama("/api/report/GetTransaction", {"transactionId": 5})[2]["data"]
		self.assertEqual(storico["id"], 5)
		self.assertIn("piecesIn", storico)
		vuoto = self.chiama("/api/report/GetTransaction", {"transactionId": 99999})[2]["data"]
		self.assertEqual(vuoto["operation"], "")
		filtro = {"startTime": "2000-01-01 00:00:00", "operations": {"payment": True}}
		elenco = self.chiama("/api/report/GetTransactions", filtro)[2]["data"]
		for voce in elenco:
			self.assertEqual(voce["operation"], "payment")
		self.assertEqual(self.chiama("/api/report/GetCountability", {})[2]["data"]["currency"], "EUR")


class ProvePagamento(BaseProva):

	def avvia(self, importo, **extra):
		corpo = {"amount": importo, "queueAllowed": False, "timeout": 0, "reason": "prova", "reference": "T1"}
		corpo.update(extra)
		return self.codice("/api/transaction/StartPayment", corpo)

	def test_pagamento_con_resto(self):
		self.assertEqual(self.avvia(500), 0)
		self.assertEqual(self.chiama("/api/device/ActiveTransaction", {})[2]["data"]["operation"], "payment")
		self.assertTrue(self.sim.dispositivo.inserisci_contante(5000))
		self.attendi_inattivo()
		ultima = self.ultima()
		self.assertEqual(ultima["requested"], 500)
		self.assertEqual(ultima["inserted"], 5000)
		self.assertEqual(ultima["dispensed"], 4500)
		self.assertEqual(ultima["notDispensed"], 0)
		self.assertEqual(ultima["end"], "normal")
		self.assertEqual(ultima["id"], 100)

	def test_altra_operazione_attiva(self):
		self.assertEqual(self.avvia(500), 0)
		self.assertEqual(self.avvia(500), 4)
		self.assertEqual(self.codice("/api/transaction/StartRefill", {}), 4)
		self.assertEqual(self.codice("/api/transaction/CancelPayment", {}), 0)
		self.attendi_inattivo()
		self.assertEqual(self.ultima()["end"], "canceled")

	def test_annulla_restituisce_il_contante(self):
		self.avvia(1000)
		self.sim.dispositivo.inserisci_contante(500)
		self.assertEqual(self.codice("/api/transaction/CancelPayment", {}), 0)
		self.attendi_inattivo()
		ultima = self.ultima()
		self.assertEqual(ultima["end"], "canceled")
		self.assertEqual(ultima["dispensed"], 500)

	def test_annulla_non_ammesso_a_importo_raggiunto(self):
		self.sim.scenario.ritardo_erogazione_ms = 400
		self.avvia(500)
		self.sim.dispositivo.inserisci_contante(1000)
		time.sleep(0.5)
		self.assertEqual(self.codice("/api/transaction/CancelPayment", {}), 3)
		self.attendi_inattivo()

	def test_conferma_parziale(self):
		self.avvia(1000)
		self.assertEqual(self.codice("/api/transaction/CommitPayment", {}), 3)
		self.sim.dispositivo.inserisci_contante(500)
		self.assertEqual(self.codice("/api/transaction/CommitPayment", {}), 0)
		self.attendi_inattivo()
		self.assertEqual(self.ultima()["end"], "stopped")

	def test_timeout(self):
		self.avvia(500, timeout=1)
		self.attendi_inattivo(5)
		self.assertEqual(self.ultima()["end"], "timeout")

	def test_resto_non_erogato(self):
		self.sim.scenario.modalita_resto = modelli.RESTO_NESSUNO
		self.avvia(500)
		self.sim.dispositivo.inserisci_contante(5000)
		self.attendi_inattivo()
		ultima = self.ultima()
		self.assertEqual(ultima["end"], "normal")
		self.assertEqual(ultima["dispensed"], 0)
		self.assertEqual(ultima["notDispensed"], 4500)

	def test_resto_parziale(self):
		self.sim.scenario.modalita_resto = modelli.RESTO_PARZIALE
		self.avvia(500)
		self.sim.dispositivo.inserisci_contante(5000)
		self.attendi_inattivo()
		ultima = self.ultima()
		self.assertGreater(ultima["dispensed"], 0)
		self.assertGreater(ultima["notDispensed"], 0)
		self.assertEqual(ultima["dispensed"] + ultima["notDispensed"], 4500)

	def test_errore_dispositivo(self):
		self.sim.scenario.modalita_resto = modelli.ERRORE_DISPOSITIVO
		self.assertEqual(self.avvia(500), 6)
		info = self.chiama("/api/device/GetDeviceInfo", {})[2]["data"]
		self.assertEqual(info["statusCode"], 3)
		self.assertEqual(info["errorCode"], 1)

	def test_errore_forzato(self):
		self.sim.scenario.errore_forzato_attivo = True
		self.sim.scenario.errore_forzato_codice = 9
		self.sim.scenario.errore_forzato_messaggio = "Prova"
		risposta = self.chiama("/api/transaction/StartPayment", {"amount": 100})[2]
		self.assertEqual(risposta["code"], 9)
		self.assertEqual(risposta["message"], "Prova")

	def test_importo_negativo(self):
		self.assertEqual(self.avvia(-1), 2)

	def test_inserimento_automatico_esatto(self):
		self.sim.scenario.auto_modo = modelli.AUTO_ESATTO
		self.sim.scenario.auto_ritardo_ms = 10
		self.avvia(1230)
		self.attendi_inattivo()
		ultima = self.ultima()
		self.assertEqual(ultima["inserted"], 1230)
		self.assertEqual(ultima["dispensed"], 0)

	def test_mancanza_corrente(self):
		self.sim.scenario.mancanza_corrente_prossima = True
		self.avvia(500)
		self.attendi_inattivo()
		registro = self.chiama("/api/report/GetTransaction", {"transactionId": 100})[2]["data"]
		self.assertTrue(registro["powerFail"])
		self.assertEqual(registro["endType"], "normal")
		self.assertEqual(registro["inserted"], 0)

	def test_taglio_disabilitato_rifiutato(self):
		self.sim.dispositivo.imposta_stato_taglio(5000, "recycle", False)
		self.avvia(500)
		self.assertFalse(self.sim.dispositivo.inserisci_contante(5000))
		self.codice("/api/transaction/CancelPayment", {})
		self.attendi_inattivo()


class ProveOperazioni(BaseProva):

	def test_ricarica_fino_al_fondo(self):
		self.sim.dispositivo.azzera_livelli()
		self.assertEqual(self.codice("/api/transaction/StartRefill", {"reason": "r", "reference": "x"}), 0)
		self.assertTrue(self.sim.dispositivo.inserisci_contante(1000))
		self.assertEqual(self.codice("/api/transaction/StopRefill", {}), 0)
		self.assertEqual(self.codice("/api/transaction/StopRefill", {}), 5)
		self.assertEqual(self.ultima()["inserted"], 1000)

	def test_deposito(self):
		self.assertEqual(self.codice("/api/transaction/StartDeposit", {}), 0)
		self.sim.dispositivo.inserisci_contante(2000)
		self.assertEqual(self.codice("/api/transaction/StopDeposit", {}), 0)
		self.assertEqual(self.ultima()["inserted"], 2000)

	def test_prelievo(self):
		self.assertEqual(self.codice("/api/transaction/StartWithdrawal", {"amount": 1500}), 0)
		time.sleep(0.2)
		self.attendi_inattivo()
		ultima = self.ultima()
		self.assertEqual(ultima["requested"], 1500)
		self.assertEqual(ultima["dispensed"], 1500)

	def test_prelievo_tagli(self):
		richiesta = {"denominations": [{"value": 500, "currency": "EUR", "level": 1, "type": "note"}]}
		self.assertEqual(self.codice("/api/transaction/StartWithdrawalDenominations", richiesta), 0)
		time.sleep(0.2)
		self.attendi_inattivo()
		self.assertEqual(self.ultima()["dispensed"], 500)
		troppi = {"denominations": [{"value": 500, "currency": "EUR", "level": 99999, "type": "note"}]}
		self.assertEqual(self.codice("/api/transaction/StartWithdrawalDenominations", troppi), 8)

	def test_svuota_monete_e_cassaforte(self):
		self.sim.scenario.ritardo_erogazione_ms = 1
		self.assertEqual(self.codice("/api/transaction/StartEmptyCoins", {}), 0)
		time.sleep(0.3)
		self.attendi_inattivo(30)
		for livello in self.chiama("/api/device/AllLevels", {})[2]["data"]:
			if livello["type"] == "coin":
				self.assertEqual(livello["level"], 0)
		self.assertEqual(self.codice("/api/transaction/StartEmptyCashboxNotes", {}), 0)
		time.sleep(0.3)
		self.attendi_inattivo(30)
		for livello in self.chiama("/api/device/AllLevels", {})[2]["data"]:
			if livello["routing"] == "cashbox":
				self.assertEqual(livello["level"], 0)

	def test_chiusura_cassa(self):
		importo = self.chiama("/api/transaction/RegisterClosureAmount", None, metodo="GET")[2]
		self.assertEqual(importo["code"], 0)
		self.assertIn("amount", importo["data"])
		dettagli = self.chiama("/api/transaction/RegisterClosureDetails", None, metodo="GET")[2]
		self.assertEqual(dettagli["code"], 0)

	def test_impostazioni_tagli(self):
		stati = self.chiama("/api/settings/denomination/GetCoinDenominationStatus", {})[2]["data"]["denominations"]
		self.assertEqual(len(stati), 7)
		richiesta = {"denominations": [{"value": 2, "currency": "EUR", "status": False}]}
		self.assertEqual(self.codice("/api/settings/denomination/SetCoinDenominationStatus", richiesta), 0)
		stati = self.chiama("/api/settings/denomination/GetCoinDenominationStatus", {})[2]["data"]["denominations"]
		self.assertFalse(stati[0]["status"])
		fondo = {"denominations": [{"value": 2, "currency": "EUR", "level": 7}]}
		self.assertEqual(self.codice("/api/settings/denomination/SetFloatLevelCoins", fondo), 0)

	def test_porta(self):
		self.assertEqual(self.chiama("/api/door/Status", {})[2]["data"]["main"], False)
		self.assertEqual(self.codice("/api/door/Open", {"main": True}), 0)
		self.assertEqual(self.chiama("/api/door/Status", {})[2]["data"]["main"], True)
		self.assertEqual(self.codice("/api/door/Open", {"drawer": True}), 7)

	def test_profilo(self):
		percorso = os.path.join(tempfile.mkdtemp(), "p.json")
		self.sim.scenario.modalita_resto = modelli.RESTO_PARZIALE
		self.sim.dispositivo.imposta_livello(500, "recycle", 77)
		self.sim.salva_profilo(percorso)
		self.sim.scenario.modalita_resto = modelli.RESTO_TUTTO
		self.sim.dispositivo.imposta_livello(500, "recycle", 1)
		self.sim.carica_profilo(percorso)
		self.assertEqual(self.sim.scenario.modalita_resto, modelli.RESTO_PARZIALE)
		indice = self.sim.dispositivo.trova_denominazione(500, "recycle")
		self.assertEqual(self.sim.dispositivo.denominazioni[indice].livello, 77)


class ProveRobustezza(BaseProva):
	# Regressioni dei difetti emersi dalla revisione del codice.

	def test_nessun_doppio_archivio_durante_il_resto(self):
		self.sim.scenario.ritardo_erogazione_ms = 300
		prima = len(self.sim.dispositivo.storico)
		self.codice("/api/transaction/StartPayment", {"amount": 500})
		self.sim.dispositivo.inserisci_contante(5000)
		time.sleep(0.6)
		self.assertEqual(self.codice("/api/transaction/CancelPayment", {}), 3)
		self.assertEqual(self.codice("/api/transaction/CommitPayment", {}), 3)
		self.attendi_inattivo()
		self.assertEqual(len(self.sim.dispositivo.storico), prima + 1)
		self.assertEqual(self.ultima()["end"], "normal")

	def test_inserimento_rifiutato_a_importo_raggiunto(self):
		self.sim.scenario.ritardo_erogazione_ms = 300
		self.codice("/api/transaction/StartPayment", {"amount": 500})
		self.sim.dispositivo.inserisci_contante(1000)
		time.sleep(0.5)
		self.assertFalse(self.sim.dispositivo.inserisci_contante(500))
		self.attendi_inattivo()

	def test_operazione_asincrona_visibile_subito(self):
		self.assertEqual(self.codice("/api/transaction/StartWithdrawal", {"amount": 200}), 0)
		self.assertEqual(self.chiama("/api/device/ActiveTransaction", {})[2]["data"]["operation"], "withdrawal")
		self.assertEqual(self.codice("/api/transaction/StartPayment", {"amount": 100}), 4)
		self.assertEqual(self.codice("/api/transaction/StartWithdrawal", {"amount": 100}), 4)
		self.attendi_inattivo()

	def test_importi_negativi_rifiutati(self):
		dispositivo = self.sim.dispositivo
		self.assertEqual(dispositivo.richiedi_pagamento(500, False, "", "", 0, 0, "10.0.0.1"), (0, "No error"))
		corpo = {"amount": -5000, "queueAllowed": True}
		self.assertEqual(self.codice("/api/transaction/StartPayment", corpo), 2)
		self.assertEqual(len(dispositivo.coda), 0)
		self.assertEqual(self.codice("/api/transaction/StartPayment", {"amount": 5, "timeout": -1}), 2)
		dispositivo.annulla_transazione()
		self.attendi_inattivo()
		self.assertEqual(self.codice("/api/transaction/StartWithdrawal", {"amount": -5}), 2)

	def test_annullo_di_un_client_in_coda_non_tocca_il_pagamento_attivo(self):
		dispositivo = self.sim.dispositivo
		dispositivo.richiedi_pagamento(500, False, "", "", 0, 0, "10.0.0.1")
		self.assertEqual(dispositivo.richiedi_pagamento(300, True, "", "", 0, 0, "10.0.0.2"), (0, "No error"))
		self.assertEqual(dispositivo.richiedi_pagamento(300, True, "", "", 0, 0, "10.0.0.3"), (0, "No error"))
		self.assertEqual(dispositivo.annulla_pagamento_client("10.0.0.2"), (0, "No error"))
		self.assertEqual(dispositivo.stato, "payment")
		self.assertEqual(len(dispositivo.coda), 1)
		self.assertEqual(dispositivo.coda[0]["origine"], "10.0.0.3")
		self.assertEqual(dispositivo.coda[0]["posizione"], 1)
		dispositivo.annulla_transazione()
		time.sleep(0.4)
		self.assertEqual(dispositivo.attiva.origine, "10.0.0.3")
		dispositivo.annulla_transazione()
		self.attendi_inattivo()

	def test_prelievo_per_tagli_conta_i_pezzi_non_erogati(self):
		dispositivo = self.sim.dispositivo
		dispositivo.imposta_livello(5000, "recycle", 0)
		dispositivo.imposta_livello(2000, "recycle", 5)
		elenco = [{"value": 5000, "level": 1}, {"value": 2000, "level": 1}]
		self.assertIsNotNone(dispositivo.avvia_prelievo_tagli(elenco, "", ""))
		self.attendi_inattivo()
		ultima = self.ultima()
		self.assertEqual(ultima["dispensed"], 2000)
		self.assertEqual(ultima["notDispensed"], 5000)

	def test_livelli_negativi_rifiutati(self):
		negativo = {"denominations": [{"value": 500, "currency": "EUR", "level": -5, "type": "note"}]}
		self.assertEqual(self.chiama("/api/transaction/StartChangeDenominations", negativo)[0], 400)
		self.assertEqual(self.chiama("/api/transaction/StartWithdrawalDenominations", negativo)[0], 400)
		self.assertEqual(self.chiama("/api/settings/denomination/SetFloatLevelCoins", negativo)[0], 400)
		stato_falso = {"denominations": [{"value": 2, "currency": "EUR", "status": "false"}]}
		self.assertEqual(self.chiama("/api/settings/denomination/SetCoinDenominationStatus", stato_falso)[0], 400)

	def test_input_ostili_non_uccidono_il_filo(self):
		api = self.sim.api
		for testo in ('{"amount": NaN}', '{"amount": 1e999}', "[" * 100000, '{"amount": 1.5}', "[1]"):
			risposta = api.elabora("POST", "/api/transaction/StartPayment", {"Authorization": "Bearer " + self.token}, testo.encode(), "1.2.3.4")
			self.assertIn(risposta.stato, (200, 400))
		risposta = api.elabora("POST", "/api/device/AllLevels", {"Authorization": "Bearer caff\u00e8"}, b"", "1.2.3.4")
		self.assertEqual(risposta.stato, 401)

	def test_eccezione_imprevista_da_500(self):
		def rotto(dati, ip):
			raise RuntimeError("prova")
		self.sim.api.rotte["/api/device/AllLevels"] = ("POST", rotto, True)
		self.assertEqual(self.chiama("/api/device/AllLevels", {})[0], 500)

	def test_ferma_server_chiude_l_operazione_e_la_connessione(self):
		self.codice("/api/transaction/StartPayment", {"amount": 500})
		connessione = http.client.HTTPConnection("127.0.0.1", self.sim.server.porta, timeout=5)
		connessione.request("POST", "/api/device/AllLevels", "{}", {"Authorization": "Bearer " + self.token})
		connessione.getresponse().read()
		porta = self.sim.server.porta
		self.sim.ferma_server()
		self.assertEqual(self.sim.dispositivo.stato, "idle")
		with self.assertRaises(OSError):
			connessione.request("POST", "/api/device/AllLevels", "{}", {"Authorization": "Bearer " + self.token})
			connessione.getresponse().read()
		connessione.close()
		self.sim.avvia_server(0, False)
		self.assertEqual(self.codice("/api/transaction/StartPayment", {"amount": 500}), 0)

	def test_corpo_troppo_grande(self):
		connessione = http.client.HTTPConnection("127.0.0.1", self.sim.server.porta, timeout=5)
		connessione.putrequest("POST", "/api/device/AllLevels")
		connessione.putheader("Content-Length", str(50 * 1024 * 1024))
		connessione.putheader("Authorization", "Bearer " + self.token)
		connessione.endheaders()
		self.assertEqual(connessione.getresponse().status, 413)
		connessione.close()

	def test_password_mascherata_nel_registro(self):
		cartella = self.sim.registro.cartella
		self.chiama("/api/user/Login", {"username": "cashmatic", "password": "segretissima"}, None)
		contenuto = ""
		for nome in os.listdir(cartella):
			with open(os.path.join(cartella, nome), "r", encoding="utf-8") as file:
				contenuto += file.read()
		self.assertNotIn("segretissima", contenuto)
		self.assertIn('"password":"***"', contenuto.replace(" ", ""))
		eventi = []
		while not self.sim.registro.eventi.empty():
			eventi.append(self.sim.registro.eventi.get_nowait())
		for evento in eventi:
			self.assertNotIn("segretissima", evento.get("corpo", ""))

	def test_coda_registro_limitata(self):
		registro = self.sim.registro
		for numero in range(registro.eventi.maxsize + 50):
			registro.notifica({"n": numero})
		self.assertEqual(registro.eventi.qsize(), registro.eventi.maxsize)
		self.assertEqual(registro.eventi.get_nowait()["n"], 50)

	def test_profili_non_validi_non_alterano_lo_stato(self):
		cartella = tempfile.mkdtemp()
		percorso = os.path.join(cartella, "rotto.json")
		with open(percorso, "w", encoding="utf-8") as file:
			json.dump({"scenario": {"percentuale_errori_500": "x"}, "livelli": []}, file)
		with self.assertRaises(ValueError):
			self.sim.carica_profilo(percorso)
		self.assertEqual(self.sim.scenario.percentuale_errori_500, 0)
		with open(percorso, "w", encoding="utf-8") as file:
			json.dump({"scenario": {"modalita_resto": 2}, "livelli": [{"value": 5}]}, file)
		prima = len(self.sim.dispositivo.denominazioni)
		with self.assertRaises(ValueError):
			self.sim.carica_profilo(percorso)
		self.assertEqual(len(self.sim.dispositivo.denominazioni), prima)
		self.assertEqual(self.sim.scenario.modalita_resto, 0)

	def test_certificato_rigenerato_con_permessi_riservati(self):
		from cts_sim import certificato
		percorso = os.path.join(tempfile.mkdtemp(), "prova.pem")
		esito, messaggio = certificato.genera_certificato(percorso)
		if not esito:
			self.skipTest(messaggio)
		self.assertEqual(os.stat(percorso).st_mode & 0o777, 0o600)
		self.assertFalse(certificato.e_scaduto(percorso))
		self.assertEqual(sorted(os.listdir(os.path.dirname(percorso))), ["prova.pem"])


if __name__ == "__main__":
	unittest.main()
