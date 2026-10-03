# Simulatore CashMatic

Simulatore in Python della cassa automatica per contanti CashMatic (modello SelfPay). Riproduce il servizio di rete che il dispositivo espone ai programmi di cassa: gli stessi indirizzi, gli stessi messaggi, gli stessi codici di errore e lo stesso modo di gestire monete, banconote, resto e cassaforte.

Serve a sviluppare e collaudare un programma di cassa senza avere il dispositivo davanti, e a provare con calma i casi difficili che sul dispositivo vero sono rari o pericolosi da riprodurre: resto che non esce, mancanza di corrente, rete instabile, scadenza dell'autorizzazione.

| Voce | Valore |
|---|---|
| Versione | 1.0.0 |
| Data | 2026-10-03 |
| Linguaggio | Python 3.8 o successivo, solo libreria standard |
| Interfaccia grafica | Tkinter (facoltativa) |
| Porta predefinita | 50301 (HTTPS) |
| Indirizzo base | `https://127.0.0.1:50301/api` |

## Indice

1. [Il dispositivo che si simula](#il-dispositivo-che-si-simula)
2. [Come si avvia](#come-si-avvia)
3. [La finestra](#la-finestra)
4. [Opzioni di prova](#opzioni-di-prova)
5. [Come funziona il servizio](#come-funziona-il-servizio)
6. [Elenco delle rotte](#elenco-delle-rotte)
7. [Come si prova un pagamento](#come-si-prova-un-pagamento)
8. [Altre operazioni di cassa](#altre-operazioni-di-cassa)
9. [Prove automatiche](#prove-automatiche)
10. [Limiti e scelte del simulatore](#limiti-e-scelte-del-simulatore)
11. [File del progetto](#file-del-progetto)

## Il dispositivo che si simula

CashMatic è una cassa automatica che riceve contanti e dà il resto da sola. Il programma di cassa non comanda i motori: chiede al dispositivo di eseguire una operazione e ne legge lo stato finché non ha finito.

### Tagli e contenitori

Tutti gli importi sono interi in **centesimi** (500 vuol dire 5,00 euro). La valuta è sempre `EUR`.

| Contenitore | Che cosa contiene | Tagli |
|---|---|---|
| Riciclo, monete (`routing: recycle`, `type: coin`) | Monete riutilizzate per dare il resto | 2, 5, 10, 20, 50 centesimi, 1 e 2 euro. La moneta da 1 centesimo è facoltativa (vedi sotto) |
| Riciclo, banconote (`routing: recycle`, `type: note`) | Banconote riutilizzate per dare il resto | 5, 10, 20, 50 euro |
| Cassaforte (`routing: cashbox`) | Banconote che non servono più per il resto | 5, 10, 20, 50, 100, 200, 500 euro |

Per ogni taglio del riciclo il dispositivo conosce:

| Dato | Significato |
|---|---|
| `level` | Pezzi presenti adesso |
| `floatLevel` | Fondo cassa: pezzi da lasciare sempre nel dispositivo |
| `maxLevel` | Livello massimo: oltre questo numero il taglio non accetta altri pezzi |
| `status` | Taglio abilitato o disabilitato. Un taglio disabilitato non viene accettato |

Valori iniziali del simulatore: fondo di 100 pezzi per le monete e 30 per le banconote, massimo di 1500 monete, 180 banconote e 500 pezzi in cassaforte. All'avvio le giacenze sono casuali e lo storico contiene 100 operazioni di esempio.

### Operazioni

Il dispositivo fa **una operazione alla volta**. Quando è libero la sua operazione è `idle`. Ogni richiesta di avvio fatta mentre un'altra operazione è in corso riceve il codice `4` (Other operation active). Fa eccezione il pagamento, che può essere messo in coda (vedi [Pagamento](#pagamento-e-coda)).

| Operazione | Che cosa fa |
|---|---|
| `payment` | Incasso: il cliente inserisce contanti, il dispositivo calcola e dà il resto |
| `refill` | Carico: l'operatore inserisce pezzi per rifornire il riciclo, fino al fondo cassa |
| `deposit` | Versamento: contanti inseriti e conservati |
| `withdrawal` | Prelievo di un importo |
| `withdrawal_denominations` | Prelievo di una quantità precisa per ogni taglio |
| `change_denominations` | Cambio di tagli: si inserisce un importo e si ricevono i tagli richiesti |
| `empty`, `empty_coins`, `empty_notes` | Svuotamento di tutto il riciclo, solo delle monete o solo delle banconote |
| `float`, `float_coins`, `float_notes` | Riporto al fondo cassa: esce solo ciò che supera il fondo |
| `cashbox`, `cashbox_coins`, `cashbox_notes` | Svuotamento della cassaforte |
| `register_closure` | Chiusura di cassa: porta il riciclo al fondo cassa |

Nei svuotamenti e nei riporti al fondo le monete escono dal dispositivo, mentre le banconote vengono spostate in cassaforte. Ogni taglio richiede un secondo di lavoro.

### Calcolo del resto

Il resto si dà **sempre con il taglio più grande disponibile** che entra nell'importo ancora da dare. Se un taglio finisce si passa al successivo più piccolo. Se non si riesce a comporre l'importo, la parte mancante resta in `notDispensed` (resto non erogato).

### Contante accettato

Un pezzo inserito viene accettato solo se il suo taglio esiste ed è abilitato. Durante un pagamento:

- se il taglio del riciclo non ha raggiunto il massimo, il pezzo entra nel riciclo;
- se il taglio ha raggiunto il massimo e il pezzo è una banconota, finisce in cassaforte;
- se il taglio ha raggiunto il massimo e il pezzo è una moneta, viene rifiutato.

Durante un carico entrano solo i pezzi dei tagli sotto il fondo cassa.

## Come si avvia

```
python3 main.py                          # finestra grafica, HTTPS sulla porta 50301
python3 main.py --http                   # HTTP semplice, senza certificato
python3 main.py --porta 50400            # un'altra porta
python3 main.py --senza-gui              # solo il server, senza finestra
python3 main.py --indirizzo 127.0.0.1    # accetta solo connessioni dalla stessa macchina
```

Le opzioni si possono unire. Senza `--indirizzo` il server ascolta su tutte le interfacce di rete (`0.0.0.0`): usare `127.0.0.1` se non serve raggiungerlo da altre macchine.

Con la finestra aperta si preme **Avvia server**. Con `--senza-gui` il server parte subito e si ferma con `Ctrl+C`.

### Utenti di prova

Le credenziali sono nel file `utenti.json`, che si può modificare a piacere. Il file viene riletto a ogni richiesta `GetAll`.

| Utente | Password | Identificativo |
|---|---|---|
| `cashmatic` | `admin` | 0 |
| `selfpay` | `selfpay123` | 1 |
| `boss` | `boss123` | 2 |

### Certificato

Con HTTPS il server usa il file `certificati/server.pem`, che contiene certificato e chiave privata. Se è scaduto o manca, il programma propone di crearne uno nuovo, valido 10 anni, per `localhost`, `127.0.0.1` e gli indirizzi della macchina. Serve il comando `openssl`. Il file creato ha permessi `0600` e viene scritto in modo atomico.

Chi memorizza l'impronta della chiave pubblica (pinning) deve aggiornarla dopo ogni rigenerazione. Se il programma di cassa non gestisce certificati propri, usare `--http`.

### Tkinter

Su alcune distribuzioni Linux Tkinter si installa a parte (pacchetto `python3-tk` o simile). Senza Tkinter il simulatore funziona comunque con `--senza-gui`.

### Registro su file

Ogni richiesta ricevuta viene scritta nel file `Log/CS_LOG_gg_mm_aaaa.txt`, con ora, percorso e corpo. Le password del login sono sostituite da `***`, sia nel file sia nella finestra.

## La finestra

| Scheda | A cosa serve |
|---|---|
| Operazione | Mostra l'operazione in corso: importo richiesto, inserito, erogato, non erogato, posizione in coda. Qui si inseriscono i contanti premendo il taglio, si conferma un pagamento parziale e si annulla. I tagli sono attivi solo quando l'operazione aspetta contanti |
| Giacenze | Tabella dei tagli con livello, fondo, massimo e stato. Si possono generare livelli casuali, azzerarli, impostare il livello di un taglio, abilitare o disabilitare un taglio e attivare la moneta da 1 centesimo |
| Scenario ed errori | Tutte le opzioni di prova (vedi sotto) |
| Registro richieste | Elenco delle richieste ricevute con ora, percorso, esito HTTP, codice applicativo e durata. Selezionando una riga si leggono richiesta e risposta. Le richieste di controllo ripetute (`ActiveTransaction`, `GetDeviceInfo`) si possono nascondere |
| Storico | Ultime transazioni del dispositivo. Le anomalie (resto non erogato o fine diversa da `normal`) sono in rosso |
| Server e profili | Porta, HTTPS, stato del certificato, elenco utenti, salvataggio e caricamento dei profili di prova |

Il contante inserito dalla finestra equivale al contante messo a mano nell'imboccatura del dispositivo vero.

## Opzioni di prova

Si cambiano dalla scheda **Scenario ed errori**, anche mentre il server è in funzione.

| Opzione | Effetto |
|---|---|
| Resto completo | Il resto viene dato tutto, pezzo per pezzo |
| Resto parziale | Si dà circa la metà del resto e la parte rimasta finisce in `notDispensed`. La transazione chiude comunque con `end: "normal"` |
| Resto non erogato | Il contante inserito viene trattenuto e `notDispensed` contiene tutto il resto |
| Errore dispositivo | Le operazioni rispondono `code: 6` (Device error) e `GetDeviceInfo` segnala fuori servizio con `errorCode: 1` |
| Ritardo tra pezzi | Pausa in millisecondi tra un pezzo erogato e il successivo (predefinito 1000) |
| Durata del token | Minuti di validità dell'autorizzazione (predefinito 15) |
| Ritardo del login | Il login risponde dopo un tempo casuale tra minimo e massimo (predefinito tra 1400 e 1700 ms) |
| Latenza aggiuntiva | Attesa aggiunta a ogni risposta |
| Errori HTTP 500 | Percentuale di richieste che ricevono un errore 500 |
| Connessioni interrotte | Percentuale di richieste a cui il server chiude la connessione senza rispondere |
| Scadenza token | Revoca l'ultimo token emesso: la richiesta successiva riceve 401 |
| Mancanza di corrente | Il prossimo pagamento si chiude con `powerFail: true`, `endType: "normal"` e `inserted: 0` |
| Porta principale aperta | Cambia la risposta di `door/Status` |
| Errore forzato | Le operazioni di avvio rispondono sempre con il codice e il messaggio scelti |
| Inserimento automatico | Durante un pagamento il simulatore inserisce da solo i contanti: l'importo esatto oppure un elenco di valori in centesimi, con una pausa tra un inserimento e l'altro. Utile per le prove automatiche |

I **profili** (cartella `profili/`, file `.json`) salvano le opzioni di scenario insieme alle giacenze. Un profilo incompleto o con valori del tipo sbagliato viene rifiutato per intero e non lascia il simulatore a metà.

## Come funziona il servizio

### Richieste e risposte

Tutte le rotte rispondono a `POST`, tranne `RegisterClosureAmount` e `RegisterClosureDetails` che rispondono a `GET`. Il corpo è JSON. Un corpo vuoto o assente equivale a `{}`.

Ogni risposta riuscita ha questa forma:

```json
{"code": 0, "message": "No error", "data": {}}
```

Il campo `data` manca quando non ci sono dati da restituire. Le risposte non hanno l'intestazione `Content-Type`, hanno `Server: nginx/1.10.3` e `Access-Control-Allow-Origin: *`.

### Autenticazione

1. `POST /api/user/Login` con `{"username": "cashmatic", "password": "admin"}`.
2. La risposta contiene `data.token`, un token JWT firmato con HS256. Contiene il nome dell'utente e le date di inizio e di scadenza.
3. Tutte le altre richieste mandano l'intestazione `Authorization: Bearer <token>`.
4. Prima della scadenza si può chiedere un nuovo token con `RenewToken`.

Un token mancante, scaduto, revocato o non valido riceve `401` senza corpo.

### Codici applicativi

| Codice | Messaggio | Quando |
|---|---|---|
| 0 | No error | Operazione riuscita |
| 2 | Invalid parameters | Importo, timeout o mancia negativi |
| 3 | Cannot process command | Annullo di un pagamento con importo già raggiunto, conferma senza contanti inseriti, richiesta su operazione già in chiusura |
| 4 | Other operation active | Il dispositivo non è a riposo, oppure il pagamento non può essere messo in coda |
| 5 | No operation active | Stop o annullo senza che l'operazione corrispondente sia in corso |
| 6 | Device error | Il dispositivo è in errore |
| 7 | User not allowed | Apertura del cassetto |
| 8 | No denominations | Prelievo per tagli di un taglio che non ha abbastanza pezzi |
| 11 | User not found | Utente inesistente |
| 12 | User Invalid Password | Password errata |

### Altri esiti HTTP

| Esito | Quando |
|---|---|
| 400 senza corpo | JSON non valido, campo del tipo sbagliato, taglio inesistente |
| 401 senza corpo | Token mancante, scaduto, revocato o non valido |
| 404 senza corpo | Rotta inesistente. Anche una rotta con `?parametri` nell'indirizzo risponde 404: la rotta deve coincidere esattamente |
| 405 con `Allow` | Verbo sbagliato. L'intestazione `Allow` indica quello giusto |
| 413 | Corpo oltre 1 MiB, oppure presenza di `Transfer-Encoding` |
| 500 | Errore imprevisto in una rotta, oppure errore simulato dall'opzione dedicata |

### Stato di una operazione

`ActiveTransaction` descrive l'operazione in corso. I campi principali sono:

| Campo | Significato |
|---|---|
| `id` | Numero della transazione (0 se il dispositivo è a riposo o la richiesta è in coda) |
| `operation` | Nome dell'operazione, oppure `idle` |
| `requested` | Importo da incassare (comprende l'eventuale mancia) |
| `inserted` | Contante inserito finora |
| `dispensed` | Contante già dato |
| `notDispensed` | Parte che non è stato possibile dare |
| `queuePosition` | Posizione in coda, 0 se non in coda |
| `status` | Fase corrente (`running`, `stopping`, `cancelling`) |
| `denominationsInserted`, `denominationsDispensed`, `denominationsTransfered` | Pezzi inseriti, erogati e trasferiti, per taglio |

`LastTransaction` e `GetTransaction` restituiscono l'esito di una operazione conclusa. Il campo `end` (`endType` nei report) dice come è finita:

| Valore | Significato |
|---|---|
| `normal` | Il ciclo meccanico è finito |
| `stopped` | Concluso da una conferma esplicita (`CommitPayment`, `StopRefill`, `StopDeposit`) |
| `canceled` | Annullato dal cliente o per arresto del dispositivo |
| `timeout` | Scaduto il tempo concesso al pagamento |

**Attenzione:** `end: "normal"` indica soltanto la fine del ciclo meccanico. Un pagamento è regolare solo se `notDispensed == 0` e `inserted - dispensed == requested`.

### Pagamento e coda

Un pagamento si avvia con `StartPayment`. Il dispositivo aspetta i contanti e, appena `inserted` raggiunge `requested`, calcola e dà l'eventuale resto, poi chiude la transazione.

- **Timeout**: se `timeout` è maggiore di 0 e il tempo passa senza raggiungere l'importo, il pagamento si annulla da solo, il contante inserito viene restituito e la fine è `timeout`.
- **Annullo**: `CancelPayment` restituisce il contante inserito e chiude con `canceled`. Non si può annullare quando l'importo richiesto è già stato raggiunto (`code: 3`).
- **Conferma**: `CommitPayment` chiude subito il pagamento anche se l'importo non è stato raggiunto, purché sia stato inserito qualcosa. La fine è `stopped`.
- **Coda**: se arriva un secondo pagamento con `queueAllowed: true` mentre ce n'è uno in corso, viene messo in coda e parte appena il primo si chiude. Un client in coda che chiama `CancelPayment` toglie solo la propria richiesta.
- **Riconoscimento del client**: il dispositivo distingue i client dall'indirizzo IP. Dallo stesso indirizzo la coda non viene mai usata: un secondo pagamento riceve `code: 4`.
- **Mancia**: il campo `tipsAmount` si somma all'importo richiesto.

## Elenco delle rotte

Sono 64 rotte. Tutte richiedono `Authorization: Bearer <token>`, tranne `Login`.

| Area | Rotte |
|---|---|
| Utente (`/api/user/`) | Login, RenewToken, Details, GetAll, Update |
| Dispositivo (`/api/device/`) | GetDeviceInfo, AllLevels, ActiveTransaction, LastTransaction |
| Transazioni (`/api/transaction/`) | StartRefill, StopRefill, StartPayment, CancelPayment, CommitPayment, StartWithdrawal, StartEmptyAll, StartEmptyCoins, StartEmptyNotes, StartFloatAll, StartFloatCoins, StartFloatNotes, StartEmptyCashboxAll, StartEmptyCashboxCoins, StartEmptyCashboxNotes, StartWithdrawalDenominations, StartChangeDenominations, CancelChange, StartDeposit, StopDeposit, StartRegisterClosure, RegisterClosureAmount (GET), RegisterClosureDetails (GET) |
| Report (`/api/report/`) | GetTransactions, GetLastTransaction, GetTransaction, ResetCountability, GetCountability, GetConfig |
| Impostazioni tagli (`/api/settings/denomination/`) | GetSettableMaxLevelCoins, GetSettableMaxLevelNotes, GetSettableFloatLevelCoins, GetSettableFloatLevelNotes, SetFloatLevelCoins, SetFloatLevelNotes, SetMaxLevelCoins, SetMaxLevelNotes, GetCoinDenominationStatus, GetNoteDenominationStatus, SetCoinDenominationStatus, SetNoteDenominationStatus |
| Impostazioni dispositivo (`/api/settings/device/`) | StartParking, GetConfig, SetConfig, GetTrustedModeStatus, SetTrustedMode |
| Porta (`/api/door/`) | Available, Status, Open |
| Utilità (`/api/utility/`) | Poweroff, Reboot |
| Aggiornamenti (`/api/update/OS/`) | CheckUpdate, DownloadUpdate, InstallUpdate, GetUpdateStatus |

### Parametri delle richieste più usate

| Rotta | Campi del corpo |
|---|---|
| `user/Login` | `username`, `password` |
| `user/Details` | `id` |
| `transaction/StartPayment` | `amount` (centesimi), `timeout` (secondi, 0 = nessuno), `queueAllowed`, `tipsAmount`, `reason`, `reference` |
| `transaction/StartWithdrawal` | `amount`, `reason`, `reference` |
| `transaction/StartRefill`, `StartDeposit`, `StartEmpty*`, `StartFloat*`, `StartEmptyCashbox*`, `StartRegisterClosure` | `reason`, `reference` |
| `transaction/StartWithdrawalDenominations`, `StartChangeDenominations` | `denominations`: elenco di `{"value": 500, "level": 2}` con il numero di pezzi per taglio. `reason`, `reference` |
| `report/GetTransactions` | `startTime` (data da cui partire) e `operations`: oggetto con le operazioni da includere, per esempio `{"payment": true, "refill": true}` |
| `report/GetTransaction` | `transactionId` |
| `settings/denomination/Set*Level*` | `denominations`: elenco di `{"value": 500, "level": 30}` |
| `settings/denomination/Set*DenominationStatus` | `denominations`: elenco di `{"value": 500, "status": true}` |
| `settings/device/SetTrustedMode` | `enabled` |
| `door/Open` | `main`, `drawer` (l'apertura del cassetto risponde `code: 7`) |

`reason` e `reference` sono testi liberi: il primo descrive il motivo, il secondo è un riferimento del chiamante (per esempio il numero dello scontrino) e finiscono nello storico.

## Come si prova un pagamento

1. Avviare il server e fare `Login`.
2. `POST /api/transaction/StartPayment` con `{"amount": 500, "timeout": 60, "reason": "prova", "reference": "T1"}`.
3. Nella scheda Operazione premere il taglio da inserire, oppure attivare l'inserimento automatico.
4. Leggere lo stato con `ActiveTransaction` ogni 200-400 ms finché `operation` torna `idle`.
5. Leggere l'esito con `LastTransaction`.
6. Controllare che `notDispensed` sia 0 e che `inserted - dispensed` sia uguale a `requested`.

Esempio con `curl` (certificato di prova, quindi `-k`):

```
TOKEN=$(curl -sk -X POST https://127.0.0.1:50301/api/user/Login \
	-d '{"username":"cashmatic","password":"admin"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["token"])')

curl -sk -X POST https://127.0.0.1:50301/api/transaction/StartPayment \
	-H "Authorization: Bearer $TOKEN" \
	-d '{"amount":500,"timeout":60,"reason":"prova","reference":"T1"}'

curl -sk -X POST https://127.0.0.1:50301/api/device/ActiveTransaction \
	-H "Authorization: Bearer $TOKEN"
```

## Altre operazioni di cassa

- **Carico** (`StartRefill` poi `StopRefill`): si inseriscono pezzi dalla finestra e si chiude con lo stop. Entrano solo i tagli sotto il fondo cassa.
- **Versamento** (`StartDeposit` poi `StopDeposit`): come il carico, per contanti da conservare.
- **Prelievo** (`StartWithdrawal`): il dispositivo dà l'importo con il taglio più grande disponibile. Con `StartWithdrawalDenominations` si indica invece quanti pezzi di ogni taglio si vogliono. Se un taglio ha meno pezzi di quelli chiesti la risposta è `code: 8`.
- **Cambio di tagli** (`StartChangeDenominations`): si inserisce un importo e il dispositivo dà i tagli indicati. `CancelChange` restituisce quanto inserito.
- **Svuotamento e fondo cassa**: `StartEmpty*` porta fuori tutto il riciclo, `StartFloat*` solo ciò che supera il fondo. Le monete escono, le banconote passano in cassaforte.
- **Cassaforte** (`StartEmptyCashbox*`): svuota la cassaforte.
- **Chiusura di cassa** (`StartRegisterClosure`): porta il riciclo al fondo cassa. Prima si può leggere l'importo con `RegisterClosureAmount` e un riepilogo con `RegisterClosureDetails`, calcolato dallo storico (incassi, resto non erogato, carichi, versamenti, prelievi, fondo e differenza).
- **Report** (`GetTransactions`): elenco filtrabile per data e per tipo di operazione. Le date nelle liste hanno il formato `ore:minuti:secondi giorno/mese/anno`, quelle del dettaglio `anno-mese-giorno ore:minuti:secondi`.
- **Impostazioni**: livelli di fondo, livelli massimi e abilitazione dei tagli si leggono e si cambiano con le rotte `settings/denomination`. Si possono cambiare solo a dispositivo libero (altrimenti `code: 4`).

## Prove automatiche

```
python3 -m unittest discover -s tests -v
```

Le 45 prove avviano il server su una porta libera in HTTP e verificano rotte, codici, flussi di pagamento, annullo, timeout, resto parziale e non erogato, errore dispositivo, errore forzato, mancanza di corrente, inserimento automatico, operazioni di cassa, impostazioni e profili. Controllano anche i difetti trovati in revisione: chiusure doppie, importi negativi, richieste malformate, arresto del server e password nel registro. Durano circa 35 secondi perché lo svuotamento dei tagli ha una pausa fissa di un secondo per taglio.

Per eseguire una sola prova:

```
python3 -m unittest tests.test_simulatore.ProvePagamento.test_timeout
```

## Limiti e scelte del simulatore

- Il server parla HTTP/1.1. Il dispositivo reale supporta anche HTTP/2: i client che lo richiedono tornano da soli a HTTP/1.1.
- Una moneta che arriva quando il taglio è già al massimo viene rifiutata.
- Importi, timeout e mance negativi rispondono `code: 2`. I tagli con livello negativo o valore non positivo rispondono `400`.
- Le operazioni lunghe (prelievo, svuotamento, fondo, chiusura, cambio) creano la transazione prima di rispondere: `ActiveTransaction` le mostra subito e una seconda richiesta riceve `code: 4`.
- Fermando il server l'operazione in corso viene chiusa come `canceled` e le connessioni aperte vengono chiuse. Le connessioni inattive cadono dopo 30 secondi.
- Lo svuotamento in modalità "resto parziale" si ferma quando resta metà dell'importo, taglio per taglio.
- `GetCountability` restituisce valori di esempio fissi. `RegisterClosureDetails` invece calcola i valori dallo storico.
- `Poweroff` e `Reboot` non fanno nulla: mostrano solo un avviso nella finestra e nel registro.
- `Update`, `StartParking`, `ResetCountability` e gli aggiornamenti del sistema rispondono sempre con successo, senza effetto.
- Lo storico parte con 100 operazioni di esempio e vive solo in memoria: si perde alla chiusura del programma.
- Gli utenti si leggono da `utenti.json`. `GetAll` restituisce sempre identificativo 0 e usa il nome utente anche come nome e cognome.
- In più rispetto al dispositivo reale: scenari di rete, mancanza di corrente, errore forzato, inserimento automatico, profili e modalità senza finestra.

## File del progetto

| Percorso | Contenuto |
|---|---|
| `main.py` | Avvio, scelta tra finestra e modalità senza finestra |
| `cts_sim/dispositivo.py` | Motore: giacenze, inserimento, resto, svuotamenti, coda |
| `cts_sim/api.py` | Rotte, controlli e codici di risposta |
| `cts_sim/risposte.py` | Blocchi JSON delle risposte |
| `cts_sim/autenticazione.py` | Utenti e token JWT HS256 |
| `cts_sim/server.py` | Server HTTP/HTTPS con le opzioni di disturbo |
| `cts_sim/certificato.py` | Verifica e rigenerazione del certificato |
| `cts_sim/interfaccia.py` | Finestra Tk |
| `cts_sim/simulatore.py` | Collega i componenti e gestisce i profili |
| `cts_sim/modelli.py` | Tagli, transazioni e scenario di prova |
| `cts_sim/registro.py` | File di registro `Log/CS_LOG_gg_mm_aaaa.txt` e coda eventi per la finestra |
| `tests/` | Prove automatiche |
| `utenti.json` | Utenti di prova |
| `certificati/` | Certificato e chiave del server |
| `profili/` | Profili di prova salvati |
| `Log/` | Registro delle richieste (creato all'avvio) |
