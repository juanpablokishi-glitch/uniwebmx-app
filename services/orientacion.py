from core.config import RIASEC_ITEMS, IPIP_ITEMS, IPIP_LABELS, CARRERAS_RIASEC

def calcular_riasec(respuestas):
    """
    respuestas: dict {indice_item: bool}.
    Returns (puntajes_por_categoria, codigo_top3).
    """
    puntajes = {"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0}
    for i, item in enumerate(RIASEC_ITEMS):
        if respuestas.get(i):
            puntajes[item["cat"]] += 1

    # Tie-breaking order: R-I-A-S-E-C
    orden_desempate = ["R", "I", "A", "S", "E", "C"]
    ranking = sorted(puntajes.keys(), key=lambda c: (-puntajes[c], orden_desempate.index(c)))
    codigo_top3 = "".join(ranking[:3])
    return puntajes, codigo_top3

def calcular_ipip(respuestas):
    """
    respuestas: dict {indice_item: int 1-5}.
    Returns average (1-5) per trait.
    """
    acumulado = {r: [] for r in IPIP_LABELS}
    for i, item in enumerate(IPIP_ITEMS):
        valor = respuestas.get(i, 3)
        if item["signo"] == -1:
            valor = 6 - valor
        acumulado[item["rasgo"]].append(valor)
    return {r: round(sum(vals) / len(vals), 2) for r, vals in acumulado.items()}

def carreras_sugeridas_por_codigo(codigo_top3, top_n=6):
    """Orders careers from CARRERAS_RIASEC by how much they match the student's code."""
    pesos_posicion = {0: 3, 1: 2, 2: 1}  # weight based on priority (1st, 2nd, 3rd)
    resultados = []
    for carrera, codigo_carrera in CARRERAS_RIASEC.items():
        puntaje = 0
        for pos, letra in enumerate(codigo_top3):
            if letra in codigo_carrera:
                puntaje += pesos_posicion.get(pos, 0)
        if puntaje > 0:
            resultados.append((carrera, puntaje))
    resultados.sort(key=lambda x: -x[1])
    return resultados[:top_n]
