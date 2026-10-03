# Avvio del simulatore CashMatic: con interfaccia grafica Tk oppure da riga di comando.

import argparse
import os
import sys
import time

CARTELLA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CARTELLA)

from cts_sim.simulatore import PORTA_PREDEFINITA, Simulatore


def avvia_senza_interfaccia(argomenti):
	simulatore = Simulatore(CARTELLA)
	if argomenti.https and simulatore.certificato_scaduto():
		esito, messaggio = simulatore.rigenera_certificato()
		print(messaggio)
		if not esito:
			return 1
	simulatore.avvia_server(argomenti.porta, argomenti.https, argomenti.indirizzo)
	print("In ascolto su " + simulatore.server.indirizzo())
	try:
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		simulatore.ferma_server()
	return 0


def avvia_con_interfaccia(argomenti):
	from cts_sim.interfaccia import Interfaccia

	simulatore = Simulatore(CARTELLA)
	Interfaccia(simulatore, argomenti.porta, argomenti.https, argomenti.indirizzo).esegui()
	return 0


def main():
	parser = argparse.ArgumentParser(description="Simulatore CashMatic")
	parser.add_argument("--porta", type=int, default=PORTA_PREDEFINITA, help="porta di ascolto (predefinita 50301)")
	parser.add_argument("--indirizzo", default="0.0.0.0", help="indirizzo di ascolto (usa 127.0.0.1 per accettare solo la macchina locale)")
	parser.add_argument("--http", dest="https", action="store_false", help="usa HTTP semplice invece di HTTPS")
	parser.add_argument("--senza-gui", action="store_true", help="avvia solo il server, senza finestra")
	argomenti = parser.parse_args()
	if argomenti.senza_gui:
		return avvia_senza_interfaccia(argomenti)
	return avvia_con_interfaccia(argomenti)


if __name__ == "__main__":
	sys.exit(main())
