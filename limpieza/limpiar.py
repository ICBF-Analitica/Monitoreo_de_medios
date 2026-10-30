# -*- coding: utf-8 -*-
"""
limpiar.py - Corrige df_resultado_final.xlsx antes de que Google Drive lo tome (auditoria del 30-oct-2026).

main.py arma Data/df_resultado_final.xlsx (una fila por palabra con puntaje de sentimiento) y despues llama a
limpiar_datos(), que lo reemplaza por la version corregida. Mismas columnas y mismo orden, para que Drive y Power BI
sigan funcionando igual. Data/consolidado_noticias.xlsx NO se toca: es el acumulado de la v1 y se corrige cada vez.

Correcciones:
  1. Nombre del medio unificado ("Infobae", "infobae", "infobae.com"), sin mezclar medios de Colombia con otros del exterior.
  2. Ciudad y departamento con el geocodificador DIVIPOLA (palabra completa, Valle del Cauca antes que Cauca...).
  3. Se quitan las noticias del exterior (por el lugar del titular, el pais del medio, o Infobae sin ninguna pista de Colombia).
  4. "maltrato" = violencia o maltrato contra la ninez (palabras clave), no solo la palabra "maltrato".
  5. Lexico de sentimiento sin las palabras mal traducidas ("infantil", "solo", "mayor"...).
  6. Se quitan noticias del clima (El Nino / La Nina), de farandula y de otros temas que no son ninez.
  7. Se quitan filas con anos atipicos (antes de 2023).
Si algo falla, main.py conserva el archivo original: la actualizacion diaria nunca se detiene por la limpieza.
"""

import re
from pathlib import Path

import pandas as pd

from . import reglas as R
from .geocodificar import Geocodificador

RAIZ = Path(__file__).resolve().parent
DATA = RAIZ.parent / "Data"
DIVIPOLA = RAIZ / "data" / "divipola_raw.csv"
PERFIL_MEDIOS = RAIZ / "data" / "perfil_medios.csv"
MINUSCULAS = {"de", "del", "la", "las", "el", "los", "y", "e"}


def nombre_propio(texto):
    """'SAN JOSE DE CUCUTA' -> 'San Jose de Cucuta' (DIVIPOLA viene en mayusculas)."""
    if not isinstance(texto, str) or not texto:
        return ""
    palabras = texto.lower().split()
    return " ".join("D.C." if p == "d.c." else (p if (i and p in MINUSCULAS) else p.capitalize())
                    for i, p in enumerate(palabras))


# --- medios ----------------------------------------------------------------
DOMINIO = re.compile(r"^(www\.)|(\.(com|co|com\.co|net|org|es|mx|ar|pe|cl|ec|uy|info|tv|fm))+$")


def clave_medio(f):
    return DOMINIO.sub("", str(f).strip().casefold())


def cargar_perfil_medios():
    p = pd.read_csv(PERFIL_MEDIOS, dtype=str).fillna("")
    return {f: (pais, dpto) for f, pais, dpto in p[["fuente", "pais_medio", "dpto_dominante"]].values}


def tabla_medios(fuentes, perfil):
    """{fuente original: nombre unificado}. Une variantes de mayuscula, dominio y espacios, salvo que
    una sea de Colombia y otra del exterior (El Universal de Cartagena y el de Mexico)."""
    pais = {f: p for f, (p, _) in perfil.items()}
    grupos = {}
    for f in fuentes.value_counts().index:
        grupos.setdefault(re.sub(r"[^a-z0-9]", "", clave_medio(f)), []).append(f)
    destino = {}
    for variantes in grupos.values():
        subgrupos = []
        for f in variantes:  # de la mas a la menos frecuente
            p = pais.get(f, "sin_datos")
            for sub in subgrupos:
                if {p, pais.get(sub[0], "sin_datos")} != {"colombia", "exterior"}:
                    sub.append(f)
                    break
            else:
                subgrupos.append([f])
        for sub in subgrupos:
            for f in sub:
                destino[f] = sub[0]
    return destino


# --- ambito ----------------------------------------------------------------
def decidir_ambito(ubic, pais_medio):
    """Devuelve 'colombia', 'exterior' o 'ND'. Ver CODEBOOK.md del proyecto de innovacion, seccion 6."""
    if ubic["geo_precision"] in (1, 2):
        # "Cordoba", "Valencia"... a secas solo se aceptan si el medio es colombiano
        if ubic["riesgo_colision"] and pais_medio != "colombia":
            return "exterior" if pais_medio == "exterior" else "ND"
        # un pueblo pequeno nombrado por un medio extranjero suele ser un homonimo de afuera
        if pais_medio == "exterior" and not ubic["ubic_segura"]:
            return "exterior"
        return "colombia"
    if ubic["texto_exterior"]:
        return "exterior"
    if ubic["candidatos"]:  # municipio colombiano con nombre repetido
        if ubic.get("candidatos_colision") and pais_medio != "colombia":
            return "exterior" if pais_medio == "exterior" else "ND"
        return "exterior" if pais_medio == "exterior" else "colombia"
    if pais_medio in ("colombia", "exterior"):
        return pais_medio
    return "ND"


# Infobae sin ninguna pista de Colombia es su edicion regional de otros paises
SENALES_COLOMBIA = re.compile(
    r"\bcolombia\w*|\bicbf\b|\bbienestar familiar\b|\bpetro\b|\buribe turbay\b|\bfiscalia general de la nacion\b|"
    r"\bdefensoria del pueblo\b|\bprocuraduria\b|\bregistraduria\b|\bsena\b|\bideam\b|\bdane\b|\bminsalud\b|"
    r"\bministerio de defensa\b|\beln\b|\bfarc\b|\bclan del golfo\b|\bdisidencias\b|\bcongreso de la republica\b")

# --- maltrato ---------------------------------------------------------------
VIOLENCIA = re.compile(
    r"\b(maltrat|abus|violenc|agresi|abandon|violaci|violad|violador|golpiz|golpead|tortur|acoso|acosad|"
    r"explotaci|trata de|secuestr|lesion|castig|asesin|homicid|feminicid)\w*")

# --- sentimiento ------------------------------------------------------------
# palabras del lexico AFINN (ingles) mal traducidas al espanol: el puntaje no corresponde a su uso en estos titulares
MAL_TRADUCIDAS = {
    "infantil", "solo", "mayor", "Jesús", "Dios", "tipo", "tiempo", "pasado", "significado", "moda", "juvenil",
    "llegar", "cumplir", "cometer", "realizar", "asegura", "esperando", "legal", "seguro", "favor", "responsable",
    "calor", "fuerte", "rescate", "grande", "dejar",
}

# --- temas que no son ninez ---------------------------------------------------
CLIMA = re.compile(r"\b(El Niño|La Niña)\b")
CONTEXTO_CLIMA = re.compile(r"fenómeno|clima|lluvia|sequ|temporada|\bola |inundac|IDEAM|energía|racionamiento|agricult|"
                            r"cultivo|meteorol|pronóstic|invierno|verano|caudal", re.IGNORECASE)
FAMOSO = re.compile(r"\b(actriz|actor|cantante|presentador\w*|famos[oa]s?|influencer|modelo|futbolista|reality|youtuber|"
                    r"streamer|tiktoker|farandula|celebridad|reina de belleza|miss|la casa de los famosos|rapero|"
                    r"cantautor|vedette|conductor de tv)\b")
BEBE_FAMA = re.compile(r"\b(bebe|embaraz\w*|primer hij[oa]|dio a luz|nacimiento|hij[oa]|gestacion|baby shower)\b")
CRIMEN = re.compile(r"\b(muri|murio|muer|muert|mori|mat[oa]|abus|violenc|captur|accident|desaparec|secuestr|asesin|"
                    r"maltrat|denunci|agred|hospital|emergencia|tragedia|fallec|rescat|ahogad|devuelv|robad|buscan|"
                    r"carpeta de investigacion|culpable|condena|descuartiz|homicid|feminicid|arroj|quemad|lesion|"
                    r"arrest|prision|detenid|detencion)\w*")
NOMBRES_NO_NINEZ = re.compile(r"bebe rexha|nina pastori|loteria del nino|nino de rivera|\bse bebe\b|"
                              r"\bbebe (alcohol|agua|cerveza|vino|licor)\b")


def no_es_ninez(titulo, t):
    """Devuelve el motivo si la noticia es del clima (El Nino/La Nina), de farandula o de otro tema que no es ninez."""
    if CLIMA.search(titulo) and CONTEXTO_CLIMA.search(titulo):
        return "clima"
    if R.OTRO.search(t) and not CRIMEN.search(t):
        return "otro"
    if NOMBRES_NO_NINEZ.search(t):
        return "otro"
    if FAMOSO.search(t) and BEBE_FAMA.search(t) and not CRIMEN.search(t):
        return "farandula"
    return ""


# --- ciudad y departamento ------------------------------------------------------
CIUDAD_V1 = {"Bogotá, D.C.": "Bogotá", "Santiago de Cali": "Cali", "Cartagena de Indias": "Cartagena",
             "San José de Cúcuta": "Cúcuta", "San Juan de Pasto": "Pasto"}
# las 33 ciudades que ya usaba la v1 conservan su nombre corto; el resto lleva el departamento (Bing no confunde Fresno, Tolima)
CIUDADES_V1 = {"Leticia", "Medellín", "Arauca", "Barranquilla", "Cartagena", "Tunja", "Manizales", "Florencia", "Yopal",
               "Popayán", "Valledupar", "Quibdó", "Montería", "Bogotá", "Inírida", "San José del Guaviare", "Neiva",
               "Riohacha", "Santa Marta", "Villavicencio", "Pasto", "Cúcuta", "Mocoa", "Armenia", "Pereira",
               "San Andrés", "Bucaramanga", "Sincelejo", "Ibagué", "Cali", "Mitú", "Puerto Carreño"}
DEPTO_V1 = {"Archipiélago de San Andrés, Providencia y Santa Catalina": "San Andrés y Providencia"}
AMBITO = {"colombia": "Colombia", "exterior": "Exterior", "ND": "Sin determinar"}


def etiqueta_ciudad(municipio, departamento):
    m = nombre_propio(municipio)
    m = CIUDAD_V1.get(m, m)
    d = nombre_propio(departamento)
    return m if m in CIUDADES_V1 else f"{m}, {DEPTO_V1.get(d, d)}"


def limpiar_datos(entrada=DATA, salida=None):
    """Lee consolidado_noticias.xlsx y df_resultado_final.xlsx de `entrada` y escribe el df_resultado_final corregido
    en `salida` (por defecto, sobre el mismo archivo). Devuelve un resumen de lo que hizo."""
    entrada = Path(entrada)
    salida = Path(salida) if salida else entrada
    print("Limpieza: leyendo consolidado y df_resultado_final...")
    cons = pd.read_excel(entrada / "consolidado_noticias.xlsx").dropna(subset=["titulo"])
    cons["titulo"] = cons["titulo"].astype(str).str.strip()
    cons = cons.drop_duplicates("titulo")
    res = pd.read_excel(entrada / "df_resultado_final.xlsx")
    res["titulo"] = res["titulo"].astype(str).str.strip()
    n_filas0, n_tit0 = len(res), res["titulo"].nunique()
    if n_filas0 == 0 or len(cons) == 0:
        raise ValueError("df_resultado_final o consolidado vacios: no se limpia")

    perfil = cargar_perfil_medios()
    destino = tabla_medios(cons["fuente"].astype(str), perfil)
    cons["fuente_n"] = cons["fuente"].astype(str).map(destino)

    pais_n = {}  # pais de cada medio unificado: el del escrito mas frecuente que tenga dato
    for f, g in cons.groupby("fuente_n"):
        for orig in g["fuente"].value_counts().index:
            p = perfil.get(orig, ("sin_datos", ""))[0]
            if p != "sin_datos":
                pais_n[f] = p
                break
        else:
            pais_n[f] = "sin_datos"

    # solo se clasifican las noticias que estan en df_resultado_final (el resto no se publica)
    titulos = set(res["titulo"])
    cons = cons[cons["titulo"].isin(titulos)].copy()
    print(f"Limpieza: clasificando {len(cons):,} noticias...")
    geo = Geocodificador(DIVIPOLA)
    ambito, ciudad, depto = [], [], []
    for titulo, f in cons[["titulo", "fuente_n"]].values:
        u = geo.ubicar(titulo)
        amb = decidir_ambito(u, pais_n[f])
        if f == "Infobae" and amb == "ND" and not SENALES_COLOMBIA.search(R.norm(titulo)):
            amb = "exterior"
        ambito.append(AMBITO[amb])
        ciudad.append(etiqueta_ciudad(u["municipio"], u["departamento"])
                      if amb == "colombia" and u["geo_precision"] == 1 else None)
        depto.append(nombre_propio(u["departamento"])
                     if amb == "colombia" and u["geo_precision"] in (1, 2) else None)
    cons["Ambito"], cons["ciudad_n"], cons["departamento_n"] = ambito, ciudad, depto
    cons["departamento_n"] = cons["departamento_n"].replace(DEPTO_V1)

    norm = cons["titulo"].map(R.norm)
    cons["maltrato_n"] = norm.map(lambda t: int(bool(VIOLENCIA.search(t))))
    cons["excluir"] = [no_es_ninez(ti, t) for ti, t in zip(cons["titulo"], norm)]

    corr = cons.set_index("titulo")[["fuente_n", "ciudad_n", "departamento_n", "maltrato_n", "excluir", "Ambito"]]
    res = res.merge(corr, left_on="titulo", right_index=True, how="left")
    res = res[res["excluir"].fillna("") == ""]                 # clima, farandula, otros
    res = res[res["Ambito"].fillna("Sin determinar") != "Exterior"]   # noticias del exterior
    res = res[~res["tokens"].isin(MAL_TRADUCIDAS)]             # palabras mal traducidas
    res = res[res["Año"] >= 2023]                              # anos atipicos
    if res.empty:
        raise ValueError("la limpieza dejo el archivo vacio: se conserva el original")

    out = pd.DataFrame({
        "titulo": res["titulo"], "link": res["link"], "fuente": res["fuente_n"].fillna(res["fuente"]),
        "ciudad": res["ciudad_n"], "departamento": res["departamento_n"],
        "maltrato": res["maltrato_n"].fillna(0).astype(int),
        "Año": res["Año"], "Mes": res["Mes"], "DiaSemana": res["DiaSemana"], "DiaNumero": res["DiaNumero"],
        "tokens": res["tokens"], "Puntuacion": res["Puntuacion"].astype(int), "Word": res["Word"]})
    destino_xlsx = salida / "df_resultado_final.xlsx"
    temporal = salida / "df_resultado_final.tmp.xlsx"
    with pd.ExcelWriter(temporal, engine="openpyxl") as w:   # sin hipervinculos: los links largos inflan el archivo
        out.to_excel(w, index=False)
    temporal.replace(destino_xlsx)   # solo se reemplaza si el archivo nuevo se escribio completo

    tit = out.drop_duplicates("titulo")
    resumen = (f"Limpieza: {n_filas0:,} -> {len(out):,} filas | {n_tit0:,} -> {len(tit):,} noticias | "
               f"con ciudad {tit['ciudad'].notna().mean():.0%} | sin determinar o Colombia "
               f"(exterior fuera) | quitadas por tema: {int((cons['excluir'] != '').sum()):,}")
    print(resumen)
    return resumen
