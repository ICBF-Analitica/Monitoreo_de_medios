# -*- coding: utf-8 -*-
"""
registro.py - Registro de Hechos de violencia sexual contra la ninez desde las noticias (clasificacion y agrupacion).
Copia de innovacion_monitoreo_medios/src/piloto.py adaptada para correr dentro de la Action. Reglas en CODEBOOK.md del proyecto de innovacion.
"""

import re
from pathlib import Path

import pandas as pd

from . import reglas as R
from .agrupar import agrupar, consolidar
from .geocodificar import Geocodificador

RAIZ = Path(__file__).resolve().parent
DIVIPOLA = RAIZ / "data" / "divipola_raw.csv"
PERFIL_MEDIOS = RAIZ / "data" / "perfil_medios.csv"


SIN_LUGAR = {"municipio": "", "cod_divipola": "", "departamento": "", "cod_dpto": "",
             "geo_precision": 3, "lat": None, "lon": None, "mpio_grande": False}


# palabras que delatan que la noticia es de Colombia aunque el lugar no sea inequivoco ("Eln", "ICBF", "Colombia")
SENALES_COLOMBIA = re.compile(
    r"\bcolombia\w*|\bicbf\b|\bbienestar familiar\b|\beln\b|\bfarc\b|\bclan del golfo\b|\bpetro\b|\bprocuraduria\b|"
    r"\bdefensoria del pueblo\b|\bmedicina legal\b|\bgaula\b|\bsijin\b|\bdijin\b|\bfiscalia general de la nacion\b")


def cargar_perfil_medios():
    if not PERFIL_MEDIOS.exists():
        raise FileNotFoundError(f"Falta {PERFIL_MEDIOS}")
    p = pd.read_csv(PERFIL_MEDIOS, dtype=str).fillna("")
    return {f: (pais, dpto) for f, pais, dpto in p[["fuente", "pais_medio", "dpto_dominante"]].values}


def decidir_ambito(ubic, pais_medio):
    """Devuelve (ambito, criterio). Ver CODEBOOK.md, seccion 6."""
    if ubic["geo_precision"] in (1, 2):
        # "Cordoba", "Valencia"... a secas solo se aceptan si el medio es colombiano
        if ubic["riesgo_colision"] and pais_medio != "colombia":
            return ("exterior" if pais_medio == "exterior" else "ND"), "lugar_dudoso"
        # un pueblo pequeno nombrado por un medio extranjero suele ser un homonimo de afuera
        if pais_medio == "exterior" and not ubic["ubic_segura"]:
            return "exterior", "medio"
        # un lugar que no es inequivoco (un pueblo sin departamento: "Malaga", "El Dorado", "Linares"), nombrado por un
        # medio que no es colombiano o no tiene perfil, no basta para decir Colombia (auditoria 31-oct-2026)
        if pais_medio != "colombia" and not ubic["ubic_segura"] and not ubic.get("senal_colombia"):
            return "ND", "lugar_no_seguro"
        return "colombia", "lugar"
    if ubic["texto_exterior"]:
        return "exterior", "texto"
    if ubic["candidatos"]:  # municipio colombiano con nombre repetido
        if ubic.get("candidatos_colision") and pais_medio != "colombia":
            return ("exterior" if pais_medio == "exterior" else "ND"), "lugar_dudoso"
        return ("exterior", "medio") if pais_medio == "exterior" else ("colombia", "lugar")
    if pais_medio in ("colombia", "exterior"):
        return pais_medio, "medio"
    return "ND", "ND"


def cargar_viejo(ruta, desde, hasta):
    df = pd.read_excel(ruta)
    col_anio = [c for c in df.columns if c.startswith("A") and "o" in c.lower()][0]
    df = df.rename(columns={col_anio: "Anio"})
    df["fecha"] = pd.to_datetime(dict(year=df["Anio"], month=df["Mes"], day=df["DiaNumero"]),
                                 errors="coerce")
    return df[(df["fecha"] >= desde) & (df["fecha"] <= hasta)].copy()


def clasificar(df, geo, perfil):
    """Aplica el codebook a cada noticia de violencia sexual."""
    filas = []
    for fila in df.itertuples(index=False):
        t = R.norm(fila.titulo)
        subtipo = R.subtipo_violencia_sexual(t)
        if subtipo is None:
            continue
        edad = R.victima_edad(t)
        relacion, agresor_grp = R.agresor(t)
        ubic = {**geo.ubicar(fila.titulo), "senal_colombia": bool(SENALES_COLOMBIA.search(t))}
        pais_medio, dpto_medio = perfil.get(fila.fuente, ("sin_datos", ""))
        ambito, criterio = decidir_ambito(ubic, pais_medio)
        lugar_no_confirmado = ""
        if ambito != "colombia" and ubic["geo_precision"] in (1, 2):
            lugar_no_confirmado = ubic["municipio"] or ubic["departamento"]
            ubic = {**ubic, **SIN_LUGAR}
        ubic = {**ubic, "ambito": ambito}
        reg = {
            "fecha": fila.fecha, "titulo": fila.titulo, "fuente": fila.fuente, "link": fila.link,
            "texto_norm": t, "tipo_registro": R.tipo_registro(t),
            "tipo_vulneracion": "violencia_sexual", "subtipo": subtipo,
            "victima_sexo": R.victima_sexo(t), "victima_edad": edad,
            "victima_grupo_edad": R.grupo_edad(edad, t), "num_victimas": R.num_victimas(t),
            "agresor_relacion": relacion, "agresor_grupo": agresor_grp,
            "estado": R.estado(t), "muerte_victima": R.muerte_victima(t),
            **ubic,
            "ambito_criterio": criterio, "pais_medio": pais_medio,
            "lugar_no_confirmado": lugar_no_confirmado,
            # solo informativo: region que mas cubre el medio local (no reemplaza la ubicacion)
            "depto_probable_medio": dpto_medio if ambito == "colombia" and ubic["geo_precision"] == 3 else "",
        }
        # confianza = que tan completo quedo el registro (el subtipo siempre esta)
        llenos = [reg["victima_sexo"] != "ND", edad is not None, relacion != "ND",
                  {1: 1.0, 2: 0.5}.get(ubic["geo_precision"], 0.0), reg["estado"] != "ND"]
        reg["confianza"] = round((1 + sum(llenos)) / 6, 2)
        filas.append(reg)
    return pd.DataFrame(filas)


def registro_de_anio(df, geo, perfil):
    """Devuelve (registro de hechos, noticias clasificadas con su id_hecho) de las noticias `df` de un periodo."""
    notas = clasificar(df, geo, perfil)
    if notas.empty:
        return pd.DataFrame(), pd.DataFrame()
    notas = notas.reset_index().rename(columns={"index": "id_noticia"})
    hechos_notas = notas[notas["tipo_registro"] == "hecho"].sort_values("fecha").reset_index(drop=True)
    grupos = agrupar(hechos_notas, corpus=df["titulo"].map(R.norm).tolist())
    registro, id_por_grupo = consolidar(hechos_notas, grupos)
    notas["id_hecho"] = notas["id_noticia"].map(
        dict(zip(hechos_notas["id_noticia"], [id_por_grupo[g] for g in grupos])))
    return registro, notas.drop(columns=["texto_norm"])
