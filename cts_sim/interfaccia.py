# Interfaccia grafica Tk del simulatore.
# Linee guida applicate: colori in token semantici, spaziatura multipla di 4,
# dati numerici in carattere a spaziatura fissa, stati espressi con testo e non
# solo con il colore, anello di focus visibile, controlli con etichetta.

import json
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import modelli

COLORI = {
	"sfondo": "#F6F4F2",
	"superficie": "#FFFFFF",
	"testo": "#1F1A1C",
	"testo_secondario": "#5E5559",
	"bordo": "#D9D2D5",
	"accento": "#8F244E",
	"accento_scuro": "#6F1A3B",
	"su_accento": "#FFFFFF",
	"ok": "#1B6E3C",
	"avviso": "#8A5A00",
	"errore": "#B3261E",
	"selezione": "#EBD3DC",
}

SPAZIO = 8
INTERVALLO_MS = 250
LIMITE_REGISTRO = 5000
PERCORSI_RUMOROSI = ("/api/device/ActiveTransaction", "/api/device/GetDeviceInfo")

TAGLI_MONETE = (1, 2, 5, 10, 20, 50, 100, 200)
TAGLI_BANCONOTE = (500, 1000, 2000, 5000, 10000, 20000, 50000)


def euro(centesimi):
	segno = ""
	if centesimi < 0:
		segno = "-"
		centesimi = -centesimi
	return segno + "%d,%02d" % (centesimi // 100, centesimi % 100)


class Interfaccia:

	def __init__(self, simulatore, porta, https, indirizzo="0.0.0.0"):
		self.simulatore = simulatore
		self.indirizzo_ascolto = indirizzo
		self.scenario = simulatore.scenario
		self.dispositivo = simulatore.dispositivo
		self.radice = tk.Tk()
		self.radice.title("Simulatore CashMatic")
		self.radice.geometry("1180x760")
		self.radice.minsize(960, 640)
		self.radice.configure(background=COLORI["sfondo"])
		self.versione_vista = -1
		self.eventi_registro = []
		self.caselle = {}
		self.var_porta = tk.IntVar(value=porta)
		self.var_https = tk.BooleanVar(value=https)
		self.var_modalita = tk.IntVar(value=self.scenario.modalita_resto)
		self.var_nascondi_rumore = tk.BooleanVar(value=True)
		self._prepara_stile()
		self._costruisci_intestazione()
		self._costruisci_schede()
		self.radice.protocol("WM_DELETE_WINDOW", self._chiudi)
		self.radice.after(INTERVALLO_MS, self._ciclo)

	def esegui(self):
		self.radice.mainloop()

	# ---------- stile ----------

	def _prepara_stile(self):
		stile = ttk.Style(self.radice)
		stile.theme_use("clam")
		base = tkfont.nametofont("TkDefaultFont")
		base.configure(size=10)
		self.carattere_fisso = tkfont.nametofont("TkFixedFont").copy()
		self.carattere_fisso.configure(size=10)
		self.carattere_titolo = base.copy()
		self.carattere_titolo.configure(size=13, weight="bold")
		self.carattere_grande = base.copy()
		self.carattere_grande.configure(size=16, weight="bold")
		stile.configure(".", background=COLORI["sfondo"], foreground=COLORI["testo"], bordercolor=COLORI["bordo"],
			focuscolor=COLORI["accento"], lightcolor=COLORI["bordo"], darkcolor=COLORI["bordo"])
		stile.configure("TFrame", background=COLORI["sfondo"])
		stile.configure("Scheda.TFrame", background=COLORI["superficie"], relief="solid", borderwidth=1)
		stile.configure("Piano.TFrame", background=COLORI["superficie"], borderwidth=0)
		stile.configure("TLabel", background=COLORI["sfondo"], foreground=COLORI["testo"])
		stile.configure("Scheda.TLabel", background=COLORI["superficie"])
		stile.configure("Secondario.TLabel", foreground=COLORI["testo_secondario"])
		stile.configure("SchedaSec.TLabel", background=COLORI["superficie"], foreground=COLORI["testo_secondario"])
		stile.configure("Titolo.TLabel", font=self.carattere_titolo)
		stile.configure("Valore.TLabel", background=COLORI["superficie"], font=self.carattere_grande)
		stile.configure("Dato.TLabel", background=COLORI["superficie"], font=self.carattere_fisso)
		stile.configure("TButton", padding=(12, 6), background=COLORI["superficie"], foreground=COLORI["testo"])
		stile.map("TButton", background=[("active", COLORI["selezione"]), ("disabled", COLORI["sfondo"])],
			foreground=[("disabled", COLORI["testo_secondario"])])
		stile.configure("Primario.TButton", background=COLORI["accento"], foreground=COLORI["su_accento"])
		stile.map("Primario.TButton", background=[("active", COLORI["accento_scuro"]), ("disabled", COLORI["bordo"])],
			foreground=[("disabled", COLORI["testo_secondario"])])
		stile.configure("Taglio.TButton", padding=(4, 10), width=9)
		stile.configure("TNotebook", background=COLORI["sfondo"], borderwidth=0)
		stile.configure("TNotebook.Tab", padding=(16, 8), background=COLORI["sfondo"], foreground=COLORI["testo_secondario"])
		stile.map("TNotebook.Tab", background=[("selected", COLORI["superficie"])],
			foreground=[("selected", COLORI["accento"])])
		stile.configure("TLabelframe", background=COLORI["sfondo"], bordercolor=COLORI["bordo"])
		stile.configure("TLabelframe.Label", background=COLORI["sfondo"], foreground=COLORI["accento"],
			font=self.carattere_titolo)
		stile.configure("TCheckbutton", background=COLORI["sfondo"])
		stile.configure("TRadiobutton", background=COLORI["sfondo"])
		stile.configure("Treeview", background=COLORI["superficie"], fieldbackground=COLORI["superficie"],
			rowheight=24, font=self.carattere_fisso)
		stile.configure("Treeview.Heading", background=COLORI["sfondo"], font=tkfont.nametofont("TkDefaultFont"),
			padding=(6, 4))
		stile.map("Treeview", background=[("selected", COLORI["selezione"])], foreground=[("selected", COLORI["testo"])])

	# ---------- intestazione ----------

	def _costruisci_intestazione(self):
		barra = ttk.Frame(self.radice, padding=(16, 12))
		barra.pack(fill="x")
		ttk.Label(barra, text="Simulatore CashMatic", style="Titolo.TLabel").pack(side="left")
		self.etichetta_stato = ttk.Label(barra, text="Server fermo", style="Secondario.TLabel")
		self.etichetta_stato.pack(side="left", padx=(16, 0))
		self.bottone_server = ttk.Button(barra, text="Avvia server", style="Primario.TButton", command=self._alterna_server)
		self.bottone_server.pack(side="right")
		self.etichetta_certificato = ttk.Label(barra, text="", style="Secondario.TLabel")
		self.etichetta_certificato.pack(side="right", padx=16)

	def _costruisci_schede(self):
		self.schede = ttk.Notebook(self.radice)
		self.schede.pack(fill="both", expand=True, padx=16, pady=(0, 16))
		self.scheda_operazione = ttk.Frame(self.schede, padding=16)
		self.scheda_giacenze = ttk.Frame(self.schede, padding=16)
		self.scheda_scenario = ttk.Frame(self.schede, padding=16)
		self.scheda_registro = ttk.Frame(self.schede, padding=16)
		self.scheda_storico = ttk.Frame(self.schede, padding=16)
		self.scheda_server = ttk.Frame(self.schede, padding=16)
		self.schede.add(self.scheda_operazione, text="Operazione")
		self.schede.add(self.scheda_giacenze, text="Giacenze")
		self.schede.add(self.scheda_scenario, text="Scenario ed errori")
		self.schede.add(self.scheda_registro, text="Registro richieste")
		self.schede.add(self.scheda_storico, text="Storico")
		self.schede.add(self.scheda_server, text="Server e profili")
		self._scheda_operazione()
		self._scheda_giacenze()
		self._scheda_scenario()
		self._scheda_registro()
		self._scheda_storico()
		self._scheda_server()

	# ---------- scheda operazione ----------

	def _scheda_operazione(self):
		cornice = self.scheda_operazione
		cornice.columnconfigure(0, weight=1)
		cornice.columnconfigure(1, weight=2)
		sinistra = ttk.Frame(cornice, style="Scheda.TFrame", padding=16)
		sinistra.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
		ttk.Label(sinistra, text="Operazione in corso", style="Scheda.TLabel", font=self.carattere_titolo).pack(anchor="w")
		self.etichetta_operazione = ttk.Label(sinistra, text="idle", style="Valore.TLabel")
		self.etichetta_operazione.pack(anchor="w", pady=(8, 16))
		griglia = ttk.Frame(sinistra, style="Piano.TFrame")
		griglia.pack(fill="x")
		griglia.columnconfigure(1, weight=1)
		self.campi_operazione = {}
		righe = (
			("id", "Id transazione"), ("richiesto", "Richiesto (EUR)"), ("inserito", "Inserito (EUR)"),
			("erogato", "Erogato (EUR)"), ("non_erogato", "Non erogato (EUR)"), ("coda", "Posizione in coda"),
			("origine", "Client"),
		)
		indice = 0
		for chiave, testo in righe:
			ttk.Label(griglia, text=testo, style="SchedaSec.TLabel").grid(row=indice, column=0, sticky="w", pady=2)
			valore = ttk.Label(griglia, text="-", style="Dato.TLabel")
			valore.grid(row=indice, column=1, sticky="e", pady=2)
			self.campi_operazione[chiave] = valore
			indice += 1
		azioni = ttk.Frame(sinistra, style="Piano.TFrame")
		azioni.pack(fill="x", pady=(16, 0))
		self.bottone_conferma = ttk.Button(azioni, text="Conferma parziale", command=self._conferma)
		self.bottone_conferma.pack(fill="x", pady=2)
		self.bottone_annulla = ttk.Button(azioni, text="Annulla operazione", command=self._annulla)
		self.bottone_annulla.pack(fill="x", pady=2)
		destra = ttk.Frame(cornice, style="Scheda.TFrame", padding=16)
		destra.grid(row=0, column=1, sticky="nsew")
		ttk.Label(destra, text="Inserimento contante", style="Scheda.TLabel", font=self.carattere_titolo).pack(anchor="w")
		self.etichetta_inserimento = ttk.Label(destra, text="", style="SchedaSec.TLabel")
		self.etichetta_inserimento.pack(anchor="w", pady=(4, 12))
		self.pulsanti_taglio = {}
		self._gruppo_tagli(destra, "Monete", TAGLI_MONETE)
		self._gruppo_tagli(destra, "Banconote", TAGLI_BANCONOTE)

	def _gruppo_tagli(self, genitore, titolo, valori):
		ttk.Label(genitore, text=titolo, style="Scheda.TLabel").pack(anchor="w", pady=(8, 4))
		riga = ttk.Frame(genitore, style="Piano.TFrame")
		riga.pack(fill="x")
		colonna = 0
		for valore in valori:
			testo = euro(valore)
			pulsante = ttk.Button(riga, text=testo, style="Taglio.TButton",
				command=lambda v=valore: self._inserisci(v))
			pulsante.grid(row=colonna // 4, column=colonna % 4, padx=4, pady=4, sticky="ew")
			self.pulsanti_taglio[valore] = pulsante
			colonna += 1
		for indice in range(4):
			riga.columnconfigure(indice, weight=1)

	def _inserisci(self, valore):
		if not self.dispositivo.inserisci_contante(valore):
			self.etichetta_inserimento.configure(text="Taglio " + euro(valore) + " rifiutato (disabilitato, pieno o non ammesso)")
		else:
			self.etichetta_inserimento.configure(text="Inserito " + euro(valore))

	def _conferma(self):
		with self.dispositivo.blocco:
			attiva = self.dispositivo.attiva
			valida = attiva.operazione == "payment" and attiva.inserito > 0 and not attiva.in_chiusura
		if valida:
			self.dispositivo.conferma_transazione(attiva)

	def _annulla(self):
		# L'operazione da annullare e' quella vista al momento del clic: se nel
		# frattempo e' cambiata, il dispositivo non fa nulla.
		with self.dispositivo.blocco:
			attiva = self.dispositivo.attiva
			operazione = attiva.operazione
			annullabile = not attiva.in_chiusura
			if operazione == "payment" and attiva.inserito >= attiva.richiesto:
				annullabile = False
		if not annullabile:
			return
		if operazione == "payment":
			self.dispositivo._in_thread(self.dispositivo.annulla_transazione, attiva)
		if operazione == "change_denominations":
			self.dispositivo._in_thread(self.dispositivo.annulla_cambio, attiva)
		if operazione in ("refill", "deposit"):
			self.dispositivo.chiudi_transazione(attiva)

	# ---------- scheda giacenze ----------

	def _scheda_giacenze(self):
		cornice = self.scheda_giacenze
		barra = ttk.Frame(cornice)
		barra.pack(fill="x", pady=(0, 8))
		ttk.Button(barra, text="Livelli casuali", command=self.dispositivo.riempi_casuale).pack(side="left")
		ttk.Button(barra, text="Azzera livelli", command=self.dispositivo.azzera_livelli).pack(side="left", padx=8)
		self.var_1_cent = tk.BooleanVar(value=self.dispositivo.moneta_1_cent_attiva)
		ttk.Checkbutton(barra, text="Moneta da 1 centesimo", variable=self.var_1_cent,
			command=self._alterna_1_cent).pack(side="left", padx=16)
		self.etichetta_totali = ttk.Label(barra, text="", style="Secondario.TLabel")
		self.etichetta_totali.pack(side="right")
		colonne = ("tipo", "valore", "instradamento", "livello", "fondo", "massimo", "abilitato")
		titoli = ("Tipo", "Valore (EUR)", "Destinazione", "Livello", "Fondo", "Massimo", "Stato")
		self.tabella_livelli = ttk.Treeview(cornice, columns=colonne, show="headings", selectmode="browse", height=16)
		larghezze = (100, 120, 130, 90, 90, 90, 120)
		for colonna, titolo, larghezza in zip(colonne, titoli, larghezze):
			self.tabella_livelli.heading(colonna, text=titolo)
			self.tabella_livelli.column(colonna, width=larghezza, anchor="e" if colonna in ("valore", "livello", "fondo", "massimo") else "w")
		self.tabella_livelli.tag_configure("disabilitato", foreground=COLORI["testo_secondario"])
		self.tabella_livelli.tag_configure("vuoto", foreground=COLORI["errore"])
		self.tabella_livelli.pack(fill="both", expand=True)
		modifica = ttk.Frame(cornice)
		modifica.pack(fill="x", pady=(8, 0))
		ttk.Label(modifica, text="Livello del taglio selezionato").pack(side="left")
		self.var_livello = tk.IntVar(value=0)
		ttk.Spinbox(modifica, from_=0, to=5000, textvariable=self.var_livello, width=8).pack(side="left", padx=8)
		ttk.Button(modifica, text="Imposta livello", command=self._imposta_livello).pack(side="left")
		ttk.Button(modifica, text="Abilita o disabilita taglio", command=self._alterna_taglio).pack(side="left", padx=8)

	def _alterna_1_cent(self):
		self.dispositivo.alterna_moneta_1_cent(self.var_1_cent.get())

	def _taglio_selezionato(self):
		selezione = self.tabella_livelli.selection()
		if not selezione:
			messagebox.showinfo("Giacenze", "Seleziona prima un taglio nella tabella.")
			return None
		valori = self.tabella_livelli.item(selezione[0], "values")
		return selezione[0], valori

	def _chiave_taglio(self, valori):
		centesimi = int(valori[1].replace(",", ""))
		instradamento = "recycle"
		if valori[2] == "Cassaforte":
			instradamento = "cashbox"
		return centesimi, instradamento

	def _imposta_livello(self):
		scelta = self._taglio_selezionato()
		if scelta is None:
			return
		centesimi, instradamento = self._chiave_taglio(scelta[1])
		try:
			livello = int(self.var_livello.get())
		except tk.TclError:
			return
		self.dispositivo.imposta_livello(centesimi, instradamento, livello)

	def _alterna_taglio(self):
		scelta = self._taglio_selezionato()
		if scelta is None:
			return
		centesimi, instradamento = self._chiave_taglio(scelta[1])
		abilitato = scelta[1][6] == "Abilitato"
		self.dispositivo.imposta_stato_taglio(centesimi, instradamento, not abilitato)

	# ---------- scheda scenario ----------

	def _scheda_scenario(self):
		cornice = self.scheda_scenario
		cornice.columnconfigure(0, weight=1)
		cornice.columnconfigure(1, weight=1)
		resto = ttk.LabelFrame(cornice, text="Esito del resto", padding=12)
		resto.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=(0, 16))
		for codice, etichetta in modelli.ETICHETTE_MODALITA.items():
			ttk.Radiobutton(resto, text=etichetta, value=codice, variable=self.var_modalita,
				command=self._cambia_modalita).pack(anchor="w", pady=2)
		ttk.Label(resto, text="L'errore dispositivo risponde code 6 alle operazioni e segnala fuori servizio.",
			style="Secondario.TLabel", wraplength=420).pack(anchor="w", pady=(8, 0))
		tempi = ttk.LabelFrame(cornice, text="Tempi", padding=12)
		tempi.grid(row=0, column=1, sticky="nsew", pady=(0, 16))
		self._numero(tempi, 0, "Ritardo tra pezzi erogati (ms)", "ritardo_erogazione_ms", 0, 10000)
		self._numero(tempi, 1, "Durata del token (minuti)", "durata_token_min", 1, 120)
		self._numero(tempi, 2, "Ritardo login minimo (ms)", "ritardo_login_min_ms", 0, 10000)
		self._numero(tempi, 3, "Ritardo login massimo (ms)", "ritardo_login_max_ms", 0, 10000)
		rete = ttk.LabelFrame(cornice, text="Disturbi di rete", padding=12)
		rete.grid(row=1, column=0, sticky="nsew", padx=(0, 16), pady=(0, 16))
		self._numero(rete, 0, "Latenza aggiuntiva (ms)", "latenza_extra_ms", 0, 60000)
		self._numero(rete, 1, "Errori HTTP 500 (%)", "percentuale_errori_500", 0, 100)
		self._numero(rete, 2, "Connessioni interrotte (%)", "percentuale_connessioni_cadute", 0, 100)
		token = ttk.LabelFrame(cornice, text="Sessione e dispositivo", padding=12)
		token.grid(row=1, column=1, sticky="nsew", pady=(0, 16))
		ttk.Button(token, text="Scadenza token: revoca l'ultimo emesso", command=self._revoca_token).grid(row=0, column=0, sticky="w", pady=2)
		ttk.Button(token, text="Ripristina token revocati", command=self.simulatore.gestore_token.pulisci_revocati).grid(row=1, column=0, sticky="w", pady=2)
		self._casella(token, 2, "Mancanza di corrente al prossimo pagamento", "mancanza_corrente_prossima")
		self._casella(token, 3, "Porta principale aperta", "porta_aperta")
		forzato = ttk.LabelFrame(cornice, text="Errore forzato sulle operazioni", padding=12)
		forzato.grid(row=2, column=0, sticky="nsew", padx=(0, 16))
		self._casella(forzato, 0, "Rispondi sempre con questo errore", "errore_forzato_attivo")
		self._numero(forzato, 1, "Codice", "errore_forzato_codice", 1, 99)
		self._testo(forzato, 2, "Messaggio", "errore_forzato_messaggio")
		auto = ttk.LabelFrame(cornice, text="Inserimento automatico nei pagamenti", padding=12)
		auto.grid(row=2, column=1, sticky="nsew")
		self.var_auto = tk.StringVar(value=self.scenario.auto_modo)
		riga_auto = 0
		for valore, testo in ((modelli.AUTO_SPENTO, "Spento (inserisci a mano)"),
				(modelli.AUTO_ESATTO, "Importo esatto"), (modelli.AUTO_VALORI, "Elenco di valori")):
			ttk.Radiobutton(auto, text=testo, value=valore, variable=self.var_auto,
				command=self._cambia_auto).grid(row=riga_auto, column=0, columnspan=2, sticky="w")
			riga_auto += 1
		self._testo(auto, 4, "Valori in centesimi (separati da virgola)", "auto_valori")
		self._numero(auto, 5, "Pausa tra inserimenti (ms)", "auto_ritardo_ms", 0, 10000)

	def _numero(self, genitore, riga, etichetta, campo, minimo, massimo):
		ttk.Label(genitore, text=etichetta).grid(row=riga, column=0, sticky="w", pady=4)
		variabile = tk.IntVar(value=getattr(self.scenario, campo))
		spin = ttk.Spinbox(genitore, from_=minimo, to=massimo, textvariable=variabile, width=10,
			command=lambda: self._scrivi_numero(variabile, campo))
		spin.grid(row=riga, column=1, sticky="e", padx=(16, 0))
		spin.bind("<FocusOut>", lambda evento: self._scrivi_numero(variabile, campo))
		spin.bind("<Return>", lambda evento: self._scrivi_numero(variabile, campo))
		genitore.columnconfigure(0, weight=1)

	def _scrivi_numero(self, variabile, campo):
		try:
			setattr(self.scenario, campo, int(variabile.get()))
		except (tk.TclError, ValueError):
			# valore non numerico: si ripristina quello in uso
			variabile.set(getattr(self.scenario, campo))

	def _testo(self, genitore, riga, etichetta, campo):
		ttk.Label(genitore, text=etichetta).grid(row=riga, column=0, sticky="w", pady=4)
		variabile = tk.StringVar(value=str(getattr(self.scenario, campo)))
		voce = ttk.Entry(genitore, textvariable=variabile, width=22)
		voce.grid(row=riga, column=1, sticky="e", padx=(16, 0))
		variabile.trace_add("write", lambda *argomenti: setattr(self.scenario, campo, variabile.get()))
		genitore.columnconfigure(0, weight=1)

	def _casella(self, genitore, riga, testo, campo):
		variabile = tk.BooleanVar(value=getattr(self.scenario, campo))
		casella = ttk.Checkbutton(genitore, text=testo, variable=variabile,
			command=lambda: setattr(self.scenario, campo, variabile.get()))
		casella.grid(row=riga, column=0, columnspan=2, sticky="w", pady=2)
		self.caselle[campo] = variabile

	def _cambia_modalita(self):
		self.scenario.modalita_resto = self.var_modalita.get()

	def _cambia_auto(self):
		self.scenario.auto_modo = self.var_auto.get()

	def _revoca_token(self):
		ultimo = self.simulatore.gestore_token.revoca_ultimo()
		if not ultimo:
			messagebox.showinfo("Token", "Nessun token emesso finora.")

	# ---------- scheda registro ----------

	def _scheda_registro(self):
		cornice = self.scheda_registro
		barra = ttk.Frame(cornice)
		barra.pack(fill="x", pady=(0, 8))
		ttk.Button(barra, text="Svuota registro", command=self._svuota_registro).pack(side="left")
		ttk.Checkbutton(barra, text="Nascondi polling (ActiveTransaction, GetDeviceInfo)",
			variable=self.var_nascondi_rumore).pack(side="left", padx=16)
		self.etichetta_conteggio = ttk.Label(barra, text="0 richieste", style="Secondario.TLabel")
		self.etichetta_conteggio.pack(side="right")
		colonne = ("ora", "metodo", "percorso", "stato", "esito", "durata")
		titoli = ("Ora", "Metodo", "Percorso", "HTTP", "Code", "ms")
		self.tabella_registro = ttk.Treeview(cornice, columns=colonne, show="headings", selectmode="browse", height=12)
		larghezze = (90, 70, 380, 60, 160, 60)
		for colonna, titolo, larghezza in zip(colonne, titoli, larghezze):
			self.tabella_registro.heading(colonna, text=titolo)
			self.tabella_registro.column(colonna, width=larghezza, anchor="w")
		self.tabella_registro.tag_configure("errore", foreground=COLORI["errore"])
		self.tabella_registro.tag_configure("avviso", foreground=COLORI["avviso"])
		self.tabella_registro.pack(fill="both", expand=True)
		self.tabella_registro.bind("<<TreeviewSelect>>", self._mostra_dettaglio)
		self.testo_dettaglio = tk.Text(cornice, height=10, font=self.carattere_fisso, background=COLORI["superficie"],
			foreground=COLORI["testo"], relief="solid", borderwidth=1, wrap="word")
		self.testo_dettaglio.pack(fill="x", pady=(8, 0))
		self.testo_dettaglio.configure(state="disabled")

	def _svuota_registro(self):
		self.eventi_registro = []
		for voce in self.tabella_registro.get_children():
			self.tabella_registro.delete(voce)
		self.etichetta_conteggio.configure(text="0 richieste")

	def _formatta_json(self, testo):
		if not testo.strip():
			return "(vuoto)"
		try:
			return json.dumps(json.loads(testo), indent=2, ensure_ascii=False)
		except ValueError:
			return testo

	def _mostra_dettaglio(self, evento):
		selezione = self.tabella_registro.selection()
		if not selezione:
			return
		indice = int(selezione[0])
		voce = self.eventi_registro[indice]
		testo = "RICHIESTA " + voce["metodo"] + " " + voce["percorso"] + " da " + voce["ip"] + "\n"
		testo += self._formatta_json(voce["corpo"]) + "\n\nRISPOSTA HTTP " + str(voce["stato"]) + "\n"
		testo += self._formatta_json(voce["risposta"])
		self.testo_dettaglio.configure(state="normal")
		self.testo_dettaglio.delete("1.0", "end")
		self.testo_dettaglio.insert("1.0", testo)
		self.testo_dettaglio.configure(state="disabled")

	def _aggiungi_evento(self, evento):
		if evento.get("tipo") == "utility":
			messagebox.showinfo("Utility", evento["testo"])
			return
		if evento.get("tipo") == "errore":
			evento = {
				"tipo": "richiesta", "ora": "", "metodo": "ERRORE", "percorso": evento["testo"], "ip": "",
				"corpo": "", "stato": 500, "durata_ms": 0, "risposta": "",
			}
		if len(self.eventi_registro) >= LIMITE_REGISTRO:
			self._svuota_registro()
		self.eventi_registro.append(evento)
		percorso = evento["percorso"]
		if self.var_nascondi_rumore.get() and percorso in PERCORSI_RUMOROSI:
			return
		esito = ""
		etichette = ""
		try:
			dati = json.loads(evento["risposta"])
			if isinstance(dati, dict):
				esito = str(dati.get("code", "")) + " " + str(dati.get("message", ""))
		except ValueError:
			esito = ""
		etichette = ()
		if evento["stato"] >= 400 or evento["stato"] == 0:
			etichette = ("errore",)
		elif esito and not esito.startswith("0 "):
			etichette = ("avviso",)
		indice = len(self.eventi_registro) - 1
		self.tabella_registro.insert("", "end", iid=str(indice), tags=etichette, values=(
			evento["ora"], evento["metodo"], percorso, evento["stato"], esito, evento["durata_ms"]))
		self.tabella_registro.yview_moveto(1.0)
		self.etichetta_conteggio.configure(text=str(len(self.eventi_registro)) + " richieste")

	# ---------- scheda storico ----------

	def _scheda_storico(self):
		cornice = self.scheda_storico
		colonne = ("id", "operazione", "richiesto", "inserito", "erogato", "non_erogato", "fine", "inizio")
		titoli = ("Id", "Operazione", "Richiesto", "Inserito", "Erogato", "Non erogato", "Esito", "Inizio")
		self.tabella_storico = ttk.Treeview(cornice, columns=colonne, show="headings", selectmode="browse")
		larghezze = (60, 190, 100, 100, 100, 110, 90, 170)
		for colonna, titolo, larghezza in zip(colonne, titoli, larghezze):
			self.tabella_storico.heading(colonna, text=titolo)
			self.tabella_storico.column(colonna, width=larghezza, anchor="w" if colonna in ("operazione", "fine", "inizio") else "e")
		self.tabella_storico.tag_configure("anomalia", foreground=COLORI["errore"])
		scorri = ttk.Scrollbar(cornice, orient="vertical", command=self.tabella_storico.yview)
		self.tabella_storico.configure(yscrollcommand=scorri.set)
		scorri.pack(side="right", fill="y")
		self.tabella_storico.pack(fill="both", expand=True)

	# ---------- scheda server ----------

	def _scheda_server(self):
		cornice = self.scheda_server
		cornice.columnconfigure(0, weight=1)
		cornice.columnconfigure(1, weight=1)
		rete = ttk.LabelFrame(cornice, text="Connessione", padding=12)
		rete.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=(0, 16))
		ttk.Label(rete, text="Porta").grid(row=0, column=0, sticky="w", pady=4)
		self.spin_porta = ttk.Spinbox(rete, from_=1, to=65535, textvariable=self.var_porta, width=8)
		self.spin_porta.grid(row=0, column=1, sticky="e")
		self.casella_https = ttk.Checkbutton(rete, text="Usa HTTPS (consigliato)", variable=self.var_https)
		self.casella_https.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
		self.etichetta_indirizzo = ttk.Label(rete, text="", style="Secondario.TLabel", wraplength=420)
		self.etichetta_indirizzo.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)
		rete.columnconfigure(0, weight=1)
		certificato = ttk.LabelFrame(cornice, text="Certificato TLS", padding=12)
		certificato.grid(row=0, column=1, sticky="nsew", pady=(0, 16))
		self.etichetta_dettaglio_certificato = ttk.Label(certificato, text="", wraplength=420)
		self.etichetta_dettaglio_certificato.pack(anchor="w")
		ttk.Button(certificato, text="Rigenera certificato", command=self._rigenera_certificato).pack(anchor="w", pady=8)
		ttk.Label(certificato, text="Dopo la rigenerazione i client con pinning della chiave vanno aggiornati.",
			style="Secondario.TLabel", wraplength=420).pack(anchor="w")
		profili = ttk.LabelFrame(cornice, text="Profili di prova", padding=12)
		profili.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
		ttk.Label(profili, text="Un profilo salva le opzioni di scenario e le giacenze.", style="Secondario.TLabel",
			wraplength=420).pack(anchor="w")
		ttk.Button(profili, text="Salva profilo", command=self._salva_profilo).pack(anchor="w", pady=(8, 2))
		ttk.Button(profili, text="Carica profilo", command=self._carica_profilo).pack(anchor="w", pady=2)
		utenti = ttk.LabelFrame(cornice, text="Utenti (utenti.json)", padding=12)
		utenti.grid(row=1, column=1, sticky="nsew")
		self.etichetta_utenti = ttk.Label(utenti, text="", font=self.carattere_fisso, justify="left")
		self.etichetta_utenti.pack(anchor="w")
		ttk.Button(utenti, text="Ricarica elenco", command=self._aggiorna_utenti).pack(anchor="w", pady=8)
		self._aggiorna_utenti()
		self._aggiorna_certificato()

	def _aggiorna_utenti(self):
		self.simulatore.utenti.carica()
		righe = []
		for utente in self.simulatore.utenti.elenco:
			righe.append("%d  %s / %s" % (utente["id"], utente["username"], utente["password"]))
		self.etichetta_utenti.configure(text="\n".join(righe))

	def _aggiorna_certificato(self):
		from . import certificato
		scadenza = certificato.leggi_scadenza(self.simulatore.percorso_certificato)
		if scadenza is None:
			testo = "Certificato non leggibile: usa Rigenera certificato."
			breve = "Certificato assente"
		elif certificato.e_scaduto(self.simulatore.percorso_certificato):
			testo = "Certificato SCADUTO il " + scadenza.strftime("%d/%m/%Y") + ". Rigeneralo prima di avviare in HTTPS."
			breve = "Certificato scaduto"
		else:
			testo = "Certificato valido fino al " + scadenza.strftime("%d/%m/%Y") + "."
			breve = "Certificato valido"
		self.etichetta_dettaglio_certificato.configure(text=testo)
		self.etichetta_certificato.configure(text=breve)

	def _rigenera_certificato(self):
		if self.simulatore.server.attivo():
			messagebox.showinfo("Certificato", "Ferma il server prima di rigenerare il certificato.")
			return
		esito, messaggio = self.simulatore.rigenera_certificato()
		self._aggiorna_certificato()
		if esito:
			messagebox.showinfo("Certificato", messaggio)
		else:
			messagebox.showerror("Certificato", messaggio)

	def _salva_profilo(self):
		percorso = filedialog.asksaveasfilename(initialdir=self.simulatore.cartella_profili, defaultextension=".json",
			filetypes=(("Profilo", "*.json"),))
		if percorso:
			self.simulatore.salva_profilo(percorso)

	def _carica_profilo(self):
		percorso = filedialog.askopenfilename(initialdir=self.simulatore.cartella_profili, filetypes=(("Profilo", "*.json"),))
		if not percorso:
			return
		try:
			self.simulatore.carica_profilo(percorso)
		except (OSError, ValueError, KeyError) as errore:
			messagebox.showerror("Profilo", "Profilo non valido: " + str(errore))
			return
		self._rileggi_scenario()

	def _rileggi_scenario(self):
		self.var_modalita.set(self.scenario.modalita_resto)
		self.var_auto.set(self.scenario.auto_modo)
		self.var_1_cent.set(self.dispositivo.moneta_1_cent_attiva)
		for campo, variabile in self.caselle.items():
			variabile.set(getattr(self.scenario, campo))
		messagebox.showinfo("Profilo", "Profilo caricato. Riapri la scheda Scenario per vedere i valori numerici aggiornati.")

	# ---------- server ----------

	def _alterna_server(self):
		if self.simulatore.server.attivo():
			self.simulatore.ferma_server()
			self._aggiorna_intestazione()
			return
		https = self.var_https.get()
		if https and self.simulatore.certificato_scaduto():
			if not messagebox.askyesno("Certificato", "Il certificato e' scaduto o assente. Lo rigenero ora?"):
				return
			esito, messaggio = self.simulatore.rigenera_certificato()
			self._aggiorna_certificato()
			if not esito:
				messagebox.showerror("Certificato", messaggio)
				return
		try:
			self.simulatore.avvia_server(int(self.var_porta.get()), https, self.indirizzo_ascolto)
		except (OSError, ValueError, tk.TclError) as errore:
			messagebox.showerror("Server", "Avvio non riuscito: " + str(errore))
			return
		self._aggiorna_intestazione()

	def _aggiorna_intestazione(self):
		attivo = self.simulatore.server.attivo()
		if attivo:
			self.etichetta_stato.configure(text="In ascolto su " + self.simulatore.server.indirizzo(),
				foreground=COLORI["ok"])
			self.bottone_server.configure(text="Ferma server")
			self.spin_porta.state(["disabled"])
			self.casella_https.state(["disabled"])
			self.etichetta_indirizzo.configure(text="Indirizzo base: " + self.simulatore.server.indirizzo())
		else:
			self.etichetta_stato.configure(text="Server fermo", foreground=COLORI["testo_secondario"])
			self.bottone_server.configure(text="Avvia server")
			self.spin_porta.state(["!disabled"])
			self.casella_https.state(["!disabled"])
			self.etichetta_indirizzo.configure(text="")

	# ---------- aggiornamento periodico ----------

	def _ciclo(self):
		# L'aggiornamento periodico deve sopravvivere a un errore: si riprogramma sempre.
		try:
			self._svuota_coda_eventi()
			versione = self.dispositivo.versione
			if versione != self.versione_vista:
				self.versione_vista = versione
				self._aggiorna_operazione()
				self._aggiorna_livelli()
				self._aggiorna_storico()
		except Exception as errore:
			self.etichetta_stato.configure(text="Errore di aggiornamento: " + repr(errore), foreground=COLORI["errore"])
		finally:
			self.radice.after(INTERVALLO_MS, self._ciclo)

	def _svuota_coda_eventi(self):
		while True:
			try:
				evento = self.simulatore.registro.eventi.get_nowait()
			except queue.Empty:
				return
			self._aggiungi_evento(evento)

	def _aggiorna_operazione(self):
		with self.dispositivo.blocco:
			attiva = self.dispositivo.attiva
			operazione = attiva.operazione
			valori = {
				"id": str(attiva.identificativo),
				"richiesto": euro(attiva.richiesto),
				"inserito": euro(attiva.inserito),
				"erogato": euro(attiva.erogato),
				"non_erogato": euro(attiva.non_erogato),
				"coda": str(attiva.posizione_coda),
				"origine": attiva.origine or "-",
			}
			abilita = attiva.operazione in modelli.OPERAZIONI_CON_INSERIMENTO
			inserito = attiva.inserito
			presenti = {}
			for denominazione in self.dispositivo.denominazioni:
				if denominazione.stato == 1:
					presenti[denominazione.valore] = True
		self.etichetta_operazione.configure(text=operazione)
		for chiave, testo in valori.items():
			self.campi_operazione[chiave].configure(text=testo)
		for valore, pulsante in self.pulsanti_taglio.items():
			if abilita and valore in presenti:
				pulsante.state(["!disabled"])
			else:
				pulsante.state(["disabled"])
		if abilita:
			self.etichetta_inserimento.configure(text="Contante accettato: scegli un taglio da inserire.")
		else:
			self.etichetta_inserimento.configure(text="Nessuna operazione in attesa di contante.")
		if operazione == "payment" and inserito > 0:
			self.bottone_conferma.state(["!disabled"])
		else:
			self.bottone_conferma.state(["disabled"])
		if operazione in modelli.OPERAZIONI_CON_INSERIMENTO:
			self.bottone_annulla.state(["!disabled"])
		else:
			self.bottone_annulla.state(["disabled"])

	def _aggiorna_livelli(self):
		selezione = self.tabella_livelli.selection()
		memoria = ""
		if selezione:
			memoria = selezione[0]
		scorrimento = self.tabella_livelli.yview()[0]
		for voce in self.tabella_livelli.get_children():
			self.tabella_livelli.delete(voce)
		totale_riciclo = 0
		totale_cassaforte = 0
		with self.dispositivo.blocco:
			indice = 0
			for denominazione in self.dispositivo.denominazioni:
				importo = denominazione.valore * denominazione.livello
				destinazione = "Riciclo"
				if denominazione.instradamento == "cashbox":
					destinazione = "Cassaforte"
					totale_cassaforte += importo
				else:
					totale_riciclo += importo
				tipo = "Moneta"
				if denominazione.tipo == "note":
					tipo = "Banconota"
				stato = "Abilitato"
				etichette = ()
				if denominazione.stato == 0:
					stato = "Disabilitato"
					etichette = ("disabilitato",)
				elif denominazione.livello == 0 and denominazione.instradamento == "recycle":
					etichette = ("vuoto",)
				self.tabella_livelli.insert("", "end", iid=str(indice), tags=etichette, values=(
					tipo, euro(denominazione.valore), destinazione, denominazione.livello,
					denominazione.livello_fondo, denominazione.livello_max, stato))
				indice += 1
		if memoria and self.tabella_livelli.exists(memoria):
			self.tabella_livelli.selection_set(memoria)
		self.tabella_livelli.yview_moveto(scorrimento)
		self.etichetta_totali.configure(text="Riciclo EUR " + euro(totale_riciclo) + "   Cassaforte EUR " + euro(totale_cassaforte))

	def _aggiorna_storico(self):
		scorrimento = self.tabella_storico.yview()[0]
		for voce in self.tabella_storico.get_children():
			self.tabella_storico.delete(voce)
		with self.dispositivo.blocco:
			recenti = self.dispositivo.storico[-200:]
			for transazione in reversed(recenti):
				etichette = ()
				if transazione.non_erogato > 0 or transazione.fine != "normal":
					etichette = ("anomalia",)
				self.tabella_storico.insert("", "end", tags=etichette, values=(
					transazione.identificativo, transazione.operazione, euro(transazione.richiesto),
					euro(transazione.inserito), euro(transazione.erogato), euro(transazione.non_erogato),
					transazione.fine, transazione.inizio.strftime("%d/%m/%Y %H:%M:%S")))
		self.tabella_storico.yview_moveto(scorrimento)

	def _chiudi(self):
		self.simulatore.ferma_server()
		self.radice.destroy()
