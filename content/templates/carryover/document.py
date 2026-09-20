"""Cio' che la pagina non scrive e un'altra pagina dello stesso documento ha gia' detto.

`U7` non e' soltanto la promessa. Il piano la definisce piu' largamente — *leggere `data.previous()`
e portare il valore nei metadati del blocco* — e la promessa ne e' il caso in cui il valore e' un
importo. Questo modulo e' il caso in cui il valore e' **l'identita' del comparto**.

EURIZON-IT24 lo impone: la sua situazione patrimoniale non ripete di quale fondo sia, perche' il
documento ne porta uno solo e il nome sta sulla pagina degli investimenti. Attribuirlo e' legittimo
— `R7` vuole i prospetti per comparto, e di comparto ce n'e' uno — ma resta un valore **imposto**,
e `R3` vuole che chi legge il `.log.csv` lo sappia.
"""

from freeports import log
from freeports.output import Fund


def sole_fund(filter_data):
    """Il nome del comparto di cui parla il documento, se ne dichiara **uno solo**.

    Restituisce `None` quando non c'e' niente da attribuire con sicurezza — nessun fondo visto, o
    piu' d'uno — e in quel caso lo dice come errore: una pagina di prospetto che non si sa a chi
    intestare e' una riga persa, non una riga che non c'era.
    """
    names = sorted({result.name for result in filter_data if isinstance(result, Fund)})
    if not names:
        log.error(
            "this statement does not name its fund and the job has not seen one yet: "
            "there is nobody to attribute it to"
        )
        return None
    if len(names) > 1:
        log.error(
            "this statement does not name its fund and the report declares {}: "
            "attributing it to any of them would be a guess".format(len(names))
        )
        return None
    log.warn_imposed(
        field="fund",
        value=names[0],
        reason="the statement does not name it and the report declares one fund only",
    )
    return names[0]
